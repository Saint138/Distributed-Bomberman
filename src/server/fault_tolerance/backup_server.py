"""
Backup server with primary monitoring and automatic failover
"""
import socket
import threading
import pickle
import time
from typing import Tuple, Optional, Callable
from .failure_detector import FailureDetector


class BackupServer:
    """
    Backup server che:
    - Monitora il primary tramite heartbeat
    - Riceve state updates dal primary
    - Si promuove a primary in caso di fallimento
    """
    
    def __init__(self, primary_host: str, primary_port: int, 
                 heartbeat_port: int = 5565, state_port: int = 5556,
                 on_promotion: Optional[Callable] = None):
        """
        Args:
            primary_host: Host del primary server
            primary_port: Porta del primary server
            heartbeat_port: Porta per heartbeat monitoring (primary_port + 10)
            state_port: Porta DEDICATA per ricevere state updates (primary_port + 1)
            on_promotion: Callback chiamata quando diventa primary
        """
        self.primary_host = primary_host
        self.primary_port = primary_port
        self.heartbeat_port = heartbeat_port
        self.state_port = state_port
        self.on_promotion = on_promotion
        
        self.is_primary = False
        self.running = True
        self.replicated_state = None
        self.failure_detector = FailureDetector(timeout=1.5)
        
        print(f"[BACKUP] Initialized - monitoring {primary_host}:{heartbeat_port}")
        
    def start(self) -> None:
        """Avvia monitoring e state receiver"""
        monitor_thread = threading.Thread(
            target=self._monitor_primary,
            daemon=True
        )
        monitor_thread.start()
        print(f"[BACKUP] Primary monitor started")
        
        receiver_thread = threading.Thread(
            target=self._receive_state_updates,
            daemon=True
        )
        receiver_thread.start()
        print(f"[BACKUP] State receiver started on port {self.state_port}")
        
    def _monitor_primary(self) -> None:
        """
        Monitora il primary server tramite heartbeat
        Heartbeat ogni 0.5s con timeout 1.5s → rileva failure in ~2s
        """
        print(f"[BACKUP] Monitoring primary at {self.primary_host}:{self.heartbeat_port}")
        
        while not self.is_primary and self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5) 
                sock.connect((self.primary_host, self.heartbeat_port))
                sock.sendall(b"HEARTBEAT")
                response = sock.recv(1024)
                if response == b"ALIVE":
                    self.failure_detector.update_heartbeat()
                sock.close()
                
            except (ConnectionRefusedError, socket.timeout, OSError):
                pass
            except Exception as e:
                print(f"[BACKUP] Heartbeat error: {e}")
                
            if not self.failure_detector.check_primary_status():
                print("[BACKUP] WARNING: PRIMARY FAILURE DETECTED!")
                self._promote_to_primary()
                break
                
            time.sleep(0.5)  
            
    def _promote_to_primary(self) -> None:
        """
        Promuove questo backup a primary
        Dal PDF pag 29: "mascherare i fallimenti tramite ridondanza"
        """
        print("=" * 70)
        print("[BACKUP->PRIMARY] PROMOTING TO PRIMARY SERVER")
        print("=" * 70)
        
        self.is_primary = True
        
        if self.on_promotion:
            self.on_promotion(self.replicated_state)
            if self.replicated_state:
                print("[BACKUP->PRIMARY] State restored from replica")
            else:
                print("[BACKUP->PRIMARY] Starting fresh (no replicated state)")
        else:
            print("[BACKUP->PRIMARY] WARNING: No promotion callback defined!")
            
        print("[BACKUP->PRIMARY] Now serving as PRIMARY")
        
    def _handle_state_connection(self, conn, addr, update_counter_ref):
        """Gestisce una singola connessione di stato in un thread separato"""
        try:
            conn.settimeout(5.0)
            
            header = b""
            while b"\n" not in header and len(header) < 1024:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                header += chunk
                
            if b"STATE_UPDATE:" in header:
                header_line = header.split(b"\n")[0].decode('ascii')
                size_str = header_line.split(":")[1]
                state_size = int(size_str)
                
                remaining_data = header.split(b"\n", 1)[1] if b"\n" in header else b""
                state_data = remaining_data
                
                while len(state_data) < state_size:
                    chunk = conn.recv(min(8192, state_size - len(state_data)))
                    if not chunk:
                        return
                    state_data += chunk
                    
                if len(state_data) == state_size:
                    try:
                        self.replicated_state = pickle.loads(state_data)
                        update_counter_ref[0] += 1
                        if update_counter_ref[0] % 20 == 0:
                            print(f"[BACKUP] State updated (total: {update_counter_ref[0]})")
                    except Exception as e:
                        print(f"[BACKUP_ERROR] Pickle failed: {e}")
                    
        except Exception as e:
            if self.running:
                print(f"[BACKUP_ERROR] Handler error: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
    
    def _receive_state_updates(self) -> None:
        """
        Riceve aggiornamenti di stato dal primary
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.state_port))
            sock.listen(10)
            sock.settimeout(None)
            
            print(f"[BACKUP] State receiver listening on port {self.state_port}")
            update_counter_ref = [0]
            
            while not self.is_primary and self.running:
                try:
                    conn, addr = sock.accept()
                    handler_thread = threading.Thread(
                        target=self._handle_state_connection,
                        args=(conn, addr, update_counter_ref),
                        daemon=True
                    )
                    handler_thread.start()
                    
                except socket.error as e:
                    if self.running and not self.is_primary:
                        print(f"[BACKUP_ERROR] Accept error: {e}")
                    break
                        
        except Exception as e:
            print(f"[BACKUP_ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
                
    def get_replicated_state(self):
        """Ritorna lo stato replicato"""
        return self.replicated_state
        
    def stop(self) -> None:
        """Ferma il backup server"""
        print("[BACKUP] Stopping...")
        self.running = False
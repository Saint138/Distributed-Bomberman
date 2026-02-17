"""
Primary server with heartbeat responder and state replication
"""
import socket
import threading
import pickle
import time
from typing import List, Tuple, Optional


class PrimaryServer:
    """
    Primary server che implementa:
    - Heartbeat responder per failure detection
    - State replication verso backup servers
    """
    
    def __init__(self, game_service, backup_servers: List[Tuple[str, int]], 
                 heartbeat_port: int = 5556, replication_interval: float = 0.5):
        """
        Args:
            game_service: GameService instance
            backup_servers: Lista di (host, port) dei backup servers
            heartbeat_port: Porta per heartbeat responder
            replication_interval: Intervallo di replicazione in secondi
        """
        self.game_service = game_service
        self.backup_servers = backup_servers
        self.heartbeat_port = heartbeat_port
        self.replication_interval = replication_interval
        self.running = True
        self.replication_counter = 0
        
        print(f"[PRIMARY] Initialized with {len(backup_servers)} backup(s)")
        
    def start(self) -> None:
        """Avvia heartbeat responder e replication"""
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_responder,
            daemon=True
        )
        heartbeat_thread.start()
        print(f"[PRIMARY] Heartbeat responder started on port {self.heartbeat_port}")
        replication_thread = threading.Thread(
            target=self._periodic_replication,
            daemon=True
        )
        replication_thread.start()
        print(f"[PRIMARY] State replication started (interval: {self.replication_interval}s)")
        
    def _heartbeat_responder(self) -> None:
        """
        Risponde ai heartbeat requests dai backup servers
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.heartbeat_port))
            sock.listen(5)
            sock.settimeout(1.0)
            print(f"[PRIMARY] Heartbeat responder listening on port {self.heartbeat_port}")
            
            while self.running:
                try:
                    conn, addr = sock.accept()
                    data = conn.recv(1024)
                    
                    if data == b"HEARTBEAT":
                        conn.sendall(b"ALIVE")
            
                        
                    conn.close()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[PRIMARY] Heartbeat error: {e}")
                        
        except Exception as e:
            print(f"[PRIMARY] Fatal heartbeat error: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
                
    def _periodic_replication(self) -> None:
        """
        Replica lo stato periodicamente ai backup servers
        """
        while self.running:
            try:
                state_snapshot = pickle.dumps(self.game_service.state)
                successful_replications = 0
                for backup_host, backup_port in self.backup_servers:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2.0)
                        sock.connect((backup_host, backup_port))
                        state_size = len(state_snapshot)
                        header = f"STATE_UPDATE:{state_size}\n".encode()
                        sock.sendall(header + state_snapshot)
                        sock.close()
                        successful_replications += 1
                        
                    except Exception as e:
                        if self.replication_counter % 20 == 0: 
                            print(f"[PRIMARY] Replication failed to {backup_host}:{backup_port}: {e}")
                        
                self.replication_counter += 1
                if self.replication_counter % 10 == 0: 
                    print(f"[PRIMARY] State replicated to {successful_replications}/{len(self.backup_servers)} backups")
                    
            except Exception as e:
                print(f"[PRIMARY] Replication error: {e}")
                
            time.sleep(self.replication_interval)
            
    def stop(self) -> None:
        """Ferma il primary server"""
        print("[PRIMARY] Stopping...")
        self.running = False
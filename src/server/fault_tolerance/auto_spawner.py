"""
Auto spawner for automatic backup server creation
"""
import subprocess
import sys
import os
import time
import socket
from typing import Optional


class AutoSpawner:
    """
    Gestisce la creazione automatica di backup servers
    
    Quando un server diventa primary, spawna automaticamente un backup
    """
    
    def __init__(self, base_port: int = 5555):
        """
        Args:
            base_port: Porta base per i server
        """
        self.base_port = base_port
        self.backup_process: Optional[subprocess.Popen] = None
        
    def spawn_backup_server(self, primary_port: int) -> Optional[int]:
        """
        Spawna automaticamente un backup server
        
        Args:
            primary_port: Porta del primary server da monitorare
            
        Returns:
            Porta STATE RECEIVER del backup server creato, o None se fallito
        """
        state_receiver_port = primary_port + 1  # 5556
        backup_game_port = primary_port + 2     # 5557
        
        print(f"[AUTO_SPAWNER] Checking port availability...")
        print(f"[AUTO_SPAWNER]   Port {state_receiver_port} free: {self._is_port_free(state_receiver_port)}")
        print(f"[AUTO_SPAWNER]   Port {backup_game_port} free: {self._is_port_free(backup_game_port)}")
        
        if not self._is_port_free(state_receiver_port):
            print(f"[AUTO_SPAWNER] WARNING: Port {state_receiver_port} not available - cannot spawn backup!")
            return None
            
        if not self._is_port_free(backup_game_port):
            print(f"[AUTO_SPAWNER] WARNING: Port {backup_game_port} not available - cannot spawn backup!")
            return None
            
        print(f"[AUTO_SPAWNER] Spawning backup server")
        print(f"[AUTO_SPAWNER]   - Game server on port {backup_game_port}")
        print(f"[AUTO_SPAWNER]   - State receiver on port {state_receiver_port}")
        
        python_exe = 'py' if sys.platform == 'win32' else 'python3'
        
        cmd = [
            python_exe,
            '-m', 'src.server.mainServer',
            '--mode', 'backup',
            '--host', 'localhost',
            '--port', str(backup_game_port),  
            '--primary', f'localhost:{primary_port}' 
        ]
        
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                    f"backup_{backup_game_port}.log")
            log_file = open(log_path, 'w')
            
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', '..')
            )
            print(f"[AUTO_SPAWNER] Working directory: {project_root}")
            
            self.backup_process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
                cwd=project_root, 
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            print(f"[AUTO_SPAWNER] Backup server spawned (PID: {self.backup_process.pid})")
            print(f"[AUTO_SPAWNER] Backup log: {log_path}")
            
            time.sleep(0.5)
            if self.backup_process.poll() is not None:
                print(f"[AUTO_SPAWNER] WARNING: Backup server crashed immediately!")
                try:
                    log_file.flush()
                    with open(log_path, 'r') as f:
                        content = f.read()
                    if content:
                        print(f"[AUTO_SPAWNER] Backup log:\n{content}")
                except:
                    pass
                return None
            
            def _wait_for_backup():
                deadline = time.time() + 30.0 
                while time.time() < deadline:
                    time.sleep(0.5)
                    if self.backup_process.poll() is not None:
                        print(f"[AUTO_SPAWNER] WARNING: Backup server died!")
                        return
                    if not self._is_port_free(state_receiver_port):
                        elapsed = time.time() - (deadline - 30.0)
                        print(f"[AUTO_SPAWNER] Backup ready on port {state_receiver_port} in {elapsed:.1f}s")
                        return
                print(f"[AUTO_SPAWNER] WARNING: Backup never opened port {state_receiver_port}")
            
            import threading
            threading.Thread(target=_wait_for_backup, daemon=True).start()
            
            print(f"[AUTO_SPAWNER] Backup starting in background...")
            return state_receiver_port 
            
        except Exception as e:
            print(f"[AUTO_SPAWNER] ERROR: Failed to spawn backup server: {e}")
            return None
            
    def _find_free_port(self, start_port: int, max_attempts: int = 10) -> Optional[int]:
        """
        Trova una porta libera partendo da start_port
        
        Args:
            start_port: Porta da cui iniziare la ricerca
            max_attempts: Numero massimo di tentativi
            
        Returns:
            Porta libera o None se non trovata
        """
        for offset in range(max_attempts):
            port = start_port + offset
            if self._is_port_free(port):
                return port
        return None
        
    @staticmethod
    def _is_port_free(port: int) -> bool:
        """
        Verifica se una porta è libera
        
        Args:
            port: Porta da verificare
            
        Returns:
            True se la porta è libera
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False
            
    def stop_backup(self):
        """Termina il processo backup se attivo"""
        if self.backup_process and self.backup_process.poll() is None:
            print(f"[AUTO_SPAWNER] Terminating backup server (PID: {self.backup_process.pid})")
            try:
                self.backup_process.terminate()
                self.backup_process.wait(timeout=5)
            except:
                self.backup_process.kill()
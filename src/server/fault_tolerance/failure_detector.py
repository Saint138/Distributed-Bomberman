"""
Failure detector with heartbeat monitoring
"""
import time


class FailureDetector:
    """
    Rileva fallimenti del primary server tramite heartbeat
    """
    
    def __init__(self, timeout: float = 1.5):
        """
        Args:
            timeout: Tempo massimo senza heartbeat prima di dichiarare fallimento
                     1.5s: abbastanza veloce da rilevare failures, abbastanza lento
                     da non generare falsi positivi su carico elevato
        """
        self.timeout = timeout
        self.last_heartbeat = time.time()
        self.is_primary_alive = True
        
    def update_heartbeat(self) -> None:
        """Aggiorna il timestamp dell'ultimo heartbeat ricevuto"""
        self.last_heartbeat = time.time()
        self.is_primary_alive = True
        
    def check_primary_status(self) -> bool:
        """
        Verifica se il primary è ancora attivo
        Returns:
            True se il primary è vivo, False se è considerato morto
        """
        elapsed = time.time() - self.last_heartbeat
        
        if elapsed > self.timeout:
            if self.is_primary_alive:
                print(f"[FAILURE_DETECTOR] Primary timeout after {elapsed:.2f}s")
                self.is_primary_alive = False
            return False
            
        return True
        
    def reset(self) -> None:
        """Reset del detector"""
        self.last_heartbeat = time.time()
        self.is_primary_alive = True
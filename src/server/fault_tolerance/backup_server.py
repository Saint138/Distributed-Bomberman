# src/server/fault_tolerance/backup_server.py
"""
Backup server -- monitors the primary via heartbeat, promotes itself on failure.

Key invariant
-------------
When promoted this backup MUST re-open the game socket on `promoted_game_port`
(= PRIMARY_GAME_PORT, 5556) so that the proxy's fixed backend_port keeps
working with zero reconfiguration.

The promotion callback (defined in mainServer._on_promotion) is responsible
for actually opening that TCP socket.
"""
import json
import os
import socket
import sys
import threading
import time
from typing import Callable, Optional


_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
_src  = os.path.join(_root, "src")
for _p in (_root, _src):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.constants import PRIMARY_GAME_PORT, BACKUP_STATE_PORT, PRIMARY_HEARTBEAT_PORT
from server.models import state_from_dict
from .failure_detector import FailureDetector


class BackupServer:
    """
    Backup that:
    1. Opens a state-receiver socket (state_port) -- primary pushes snapshots here.
    2. Probes the primary's heartbeat port every 0.5 s.
    3. On timeout -> calls on_promotion(replicated_state).
    """

    def __init__(
        self,
        primary_host: str,
        primary_heartbeat_port: int = PRIMARY_HEARTBEAT_PORT,
        state_port: int = BACKUP_STATE_PORT,
        promoted_game_port: int = PRIMARY_GAME_PORT,
        on_promotion: Optional[Callable] = None,
    ):
        """
        Args:
            primary_host           : hostname of the primary (e.g. "localhost")
            primary_heartbeat_port : port the primary listens on for HEARTBEAT probes
                                     (e.g. 5565 = PRIMARY_GAME_PORT + 9)
            state_port             : port THIS backup listens on for state snapshots
                                     (e.g. 5557 = PRIMARY_GAME_PORT + 1)
            promoted_game_port     : port this process must serve on after promotion
                                     MUST equal the primary's game port (5556) so the
                                     proxy reconnects without reconfiguration
            on_promotion           : callback(replicated_state) invoked on promotion
        """
        self.primary_host = primary_host
        self.primary_heartbeat_port = primary_heartbeat_port
        self.state_port = state_port
        self.promoted_game_port = promoted_game_port
        self.on_promotion = on_promotion

        self.is_primary = False
        self.running = True
        self.replicated_state = None

        self.failure_detector = FailureDetector(timeout=1.5)
        self._state_sock: Optional[socket.socket] = None

        print(
            f"[BACKUP] Initialized  "
            f"heartbeat={primary_host}:{primary_heartbeat_port}  "
            f"state_port={state_port}  "
            f"promoted_game_port={promoted_game_port}"
        )

  

    def start(self) -> None:
        """Start state-receiver and heartbeat monitor threads."""
        threading.Thread(
            target=self._receive_state_updates,
            daemon=True,
            name="backup-state-recv",
        ).start()
        print(f"[BACKUP] State receiver starting on port {self.state_port}")

        threading.Thread(
            target=self._monitor_primary,
            daemon=True,
            name="backup-heartbeat-monitor",
        ).start()
        print(
            f"[BACKUP] Heartbeat monitor starting -> "
            f"{self.primary_host}:{self.primary_heartbeat_port}"
        )

    def get_replicated_state(self):
        return self.replicated_state

    def stop(self) -> None:
        print("[BACKUP] Stopping...")
        self.running = False
        if self._state_sock:
            try:
                self._state_sock.close()
            except Exception:
                pass


    def _monitor_primary(self) -> None:
        print(
            f"[BACKUP] Monitoring primary heartbeat at "
            f"{self.primary_host}:{self.primary_heartbeat_port}"
        )
        while not self.is_primary and self.running:
            self._probe_heartbeat()

            if not self.failure_detector.check_primary_status():
                print("[BACKUP] [WARN] PRIMARY FAILURE DETECTED")
                self._promote_to_primary()
                return

            time.sleep(0.5)

    def _probe_heartbeat(self) -> None:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect((self.primary_host, self.primary_heartbeat_port))
            sock.sendall(b"HEARTBEAT")
            resp = sock.recv(64)
            if resp == b"ALIVE":
                self.failure_detector.update_heartbeat()
        except (ConnectionRefusedError, socket.timeout, OSError):
            pass 
        except Exception as exc:
            print(f"[BACKUP] Heartbeat probe error: {exc}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass


    def _promote_to_primary(self) -> None:
        print("=" * 70)
        print("[BACKUP->PRIMARY] PROMOTING TO PRIMARY")
        print(f"[BACKUP->PRIMARY] Will serve on port {self.promoted_game_port}")
        if self.replicated_state:
            print("[BACKUP->PRIMARY] Replicated state available -- will restore")
        else:
            print("[BACKUP->PRIMARY] No replicated state -- starting fresh")
        print("=" * 70)

        self.is_primary = True
        if self._state_sock:
            try:
                self._state_sock.close()
            except Exception:
                pass

        if self.on_promotion:
            self.on_promotion(self.replicated_state)
        else:
            print("[BACKUP->PRIMARY] WARNING: no promotion callback set!")

    def _receive_state_updates(self) -> None:
        try:
            self._state_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._state_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._state_sock.bind(("0.0.0.0", self.state_port))
            self._state_sock.listen(10)
            print(f"[BACKUP] State receiver listening on port {self.state_port}")

            update_counter = [0]

            while not self.is_primary and self.running:
                try:
                    conn, _ = self._state_sock.accept()
                    threading.Thread(
                        target=self._handle_state_conn,
                        args=(conn, update_counter),
                        daemon=True,
                    ).start()
                except OSError:
                    break  
                except Exception as exc:
                    if self.running and not self.is_primary:
                        print(f"[BACKUP] State accept error: {exc}")
                    break

        except Exception as exc:
            print(f"[BACKUP] State receiver fatal error: {exc}")
            import traceback
            traceback.print_exc()

    def _handle_state_conn(self, conn: socket.socket, counter: list) -> None:
        """Receive one state snapshot from the primary."""
        try:
            conn.settimeout(5.0)
            header_buf = b""
            while b"\n" not in header_buf and len(header_buf) < 1024:
                chunk = conn.recv(1024)
                if not chunk:
                    return
                header_buf += chunk

            if b"STATE_UPDATE:" not in header_buf:
                return

            header_line, remainder = header_buf.split(b"\n", 1)
            state_size = int(header_line.split(b":")[1])

            payload = remainder
            while len(payload) < state_size:
                chunk = conn.recv(min(65536, state_size - len(payload)))
                if not chunk:
                    return
                payload += chunk

            if len(payload) == state_size: #try/except cattura casi e logga un messaggio invece di crashare il backup
                try:
                    self.replicated_state = state_from_dict(json.loads(payload)) # parsa i byte come JSON, ricostruisce un State
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    print(f"[BACKUP] Rejected malformed snapshot: {exc}")
                    return
                counter[0] += 1
                if counter[0] % 20 == 0:
                    print(f"[BACKUP] State updated (#{counter[0]})")

        except Exception as exc:
            if self.running and not self.is_primary:
                print(f"[BACKUP] State handler error: {exc}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
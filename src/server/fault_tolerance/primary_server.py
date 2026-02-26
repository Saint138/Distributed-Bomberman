
import socket
import threading
import pickle
import time
from typing import List, Tuple

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
_src  = os.path.join(_root, "src")
for _p in (_root, _src):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class PrimaryServer:
    """
    Implements the primary-side fault-tolerance duties:
      * Heartbeat responder  (TCP, one short-lived connection per probe)
      * Periodic state replication to every registered backup
    """

    def __init__(
        self,
        game_service,
        backup_state_ports: List[Tuple[str, int]],
        heartbeat_port: int,
        replication_interval: float = 0.1,
    ):
        """
        Args:
            game_service         : live GameService instance
            backup_state_ports   : list of (host, state_receiver_port)
                                   e.g. [("localhost", 5557)]
            heartbeat_port       : port to listen on for heartbeat probes
                                   e.g. 5565
            replication_interval : seconds between state snapshots
        """
        self.game_service = game_service
        self.backup_state_ports = list(backup_state_ports)
        self.heartbeat_port = heartbeat_port
        self.replication_interval = replication_interval
        self.running = True
        self._replication_counter = 0
        self._lock = threading.Lock()

        print(
            f"[PRIMARY] Initialized  heartbeat_port={heartbeat_port}  "
            f"backups={backup_state_ports}  interval={replication_interval}s"
        )


    def start(self) -> None:
        """Start heartbeat responder and replication threads."""
        threading.Thread(
            target=self._heartbeat_responder,
            daemon=True,
            name="primary-heartbeat",
        ).start()
        print(f"[PRIMARY] Heartbeat responder starting on port {self.heartbeat_port}")

        threading.Thread(
            target=self._periodic_replication,
            daemon=True,
            name="primary-replication",
        ).start()
        print(f"[PRIMARY] State replication starting (interval={self.replication_interval}s)")

    def add_backup(self, host: str, state_port: int) -> None:
        """Dynamically register a new backup target (thread-safe)."""
        with self._lock:
            entry = (host, state_port)
            if entry not in self.backup_state_ports:
                self.backup_state_ports.append(entry)
                print(f"[PRIMARY] Added backup target {host}:{state_port}")

    def stop(self) -> None:
        print("[PRIMARY] Stopping...")
        self.running = False

   

    def _heartbeat_responder(self) -> None:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.heartbeat_port))
            sock.listen(10)
            sock.settimeout(1.0)
            print(f"[PRIMARY] Heartbeat responder listening on port {self.heartbeat_port}")

            while self.running:
                try:
                    conn, _ = sock.accept()
                    threading.Thread(
                        target=self._handle_heartbeat_conn,
                        args=(conn,),
                        daemon=True,
                    ).start()
                except socket.timeout:
                    continue
                except Exception as exc:
                    if self.running:
                        print(f"[PRIMARY] Heartbeat accept error: {exc}")

        except Exception as exc:
            print(f"[PRIMARY] Fatal heartbeat error: {exc}")
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    @staticmethod
    def _handle_heartbeat_conn(conn: socket.socket) -> None:
        try:
            conn.settimeout(1.0)
            data = conn.recv(64)
            if data == b"HEARTBEAT":
                conn.sendall(b"ALIVE")
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    
    def _periodic_replication(self) -> None:
        while self.running:
            try:
                snapshot = pickle.dumps(self.game_service.state)
                with self._lock:
                    targets = list(self.backup_state_ports)

                ok = sum(
                    1 for host, port in targets
                    if self._send_snapshot(host, port, snapshot)
                )

                self._replication_counter += 1
                if self._replication_counter % 10 == 0:
                    print(
                        f"[PRIMARY] Replicated to {ok}/{len(targets)} backup(s)  "
                        f"(tick #{self._replication_counter})"
                    )

            except Exception as exc:
                print(f"[PRIMARY] Replication error: {exc}")

            time.sleep(self.replication_interval)

    def _send_snapshot(self, host: str, port: int, snapshot: bytes) -> bool:
        """Push one state snapshot to a backup. Returns True on success."""
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            header = f"STATE_UPDATE:{len(snapshot)}\n".encode()
            sock.sendall(header + snapshot)
            return True
        except Exception as exc:
            if self._replication_counter % 20 == 0:
                print(f"[PRIMARY] Replication failed -> {host}:{port}  ({exc})")
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

import subprocess
import sys
import os
import time
import socket
import threading
from typing import Optional

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
_src  = os.path.join(_root, "src")
for _p in (_root, _src):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.constants import PRIMARY_GAME_PORT


class AutoSpawner:
    """Spawns and monitors a backup server process."""

    def __init__(self, primary_game_port: int = PRIMARY_GAME_PORT):
        """
        Args:
            primary_game_port: Port the primary game server is listening on.
                               All backup ports are derived from this value.
        """
        self.primary_game_port = primary_game_port
        self.backup_state_port = primary_game_port + 1   # 5557
        self.backup_game_port  = primary_game_port + 2   # 5558

        self.backup_process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._respawn_enabled = True

    def spawn_backup_server(self) -> Optional[int]:
        """
        Spawn a backup server process.

        Returns:
            The state-receiver port of the new backup, or None on failure.
        """
        print("[AUTO_SPAWNER] Checking port availability...")
        for port, label in [
            (self.backup_state_port, "state-receiver"),
            (self.backup_game_port,  "backup-game"),
        ]:
            if not self._is_port_free(port):
                print(f"[AUTO_SPAWNER] [FAIL] Port {port} ({label}) already in use -- cannot spawn backup")
                return None
            print(f"[AUTO_SPAWNER] [OK] Port {port} ({label}) is free")

        return self._do_spawn()

    def stop_backup(self):
        """Terminate the backup process if it is running."""
        self._respawn_enabled = False
        if self.backup_process and self.backup_process.poll() is None:
            pid = self.backup_process.pid
            print(f"[AUTO_SPAWNER] Terminating backup server (PID {pid})...")
            try:
                self.backup_process.terminate()
                self.backup_process.wait(timeout=5)
            except Exception:
                try:
                    self.backup_process.kill()
                except Exception:
                    pass

    def _do_spawn(self) -> Optional[int]:
        """Actually launch the subprocess."""
        python_exe = "py" if sys.platform == "win32" else "python3"
        cmd = [
            python_exe,
            "-m", "src.server.mainServer",
            "--mode",          "backup",
            "--host",          "localhost",
            "--port",          str(self.backup_game_port),
            "--primary",       f"localhost:{self.primary_game_port}",
            "--promoted-port", str(self.primary_game_port),
        ]

        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"backup_{self.backup_game_port}.log",
        )

        print("[AUTO_SPAWNER] Spawning backup server...")
        print(f"[AUTO_SPAWNER]   game port      : {self.backup_game_port}")
        print(f"[AUTO_SPAWNER]   state-rcv port : {self.backup_state_port}")
        print(f"[AUTO_SPAWNER]   promoted port  : {self.primary_game_port}")
        print(f"[AUTO_SPAWNER]   log            : {log_path}")
        print(f"[AUTO_SPAWNER]   cwd            : {project_root}")

        try:
            log_file = open(log_path, "w")
            extra = {}
            if sys.platform == "win32":
                extra["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            self.backup_process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
                cwd=project_root,
                **extra,
            )
            print(f"[AUTO_SPAWNER] Backup process PID: {self.backup_process.pid}")
            time.sleep(0.5)
            if self.backup_process.poll() is not None:
                print(f"[AUTO_SPAWNER] [FAIL] Backup crashed immediately -- check {log_path}")
                return None

            threading.Thread(target=self._wait_for_ready, daemon=True).start()
            self._monitor_thread = threading.Thread(
                target=self._monitor_backup, daemon=True
            )
            self._monitor_thread.start()

            return self.backup_state_port

        except Exception as exc:
            print(f"[AUTO_SPAWNER] [FAIL] Failed to spawn backup: {exc}")
            return None

    def _wait_for_ready(self, timeout: float = 30.0):
        """Log when the backup state-receiver port becomes available."""
        deadline = time.time() + timeout
        t0 = time.time()
        while time.time() < deadline:
            if self.backup_process and self.backup_process.poll() is not None:
                print("[AUTO_SPAWNER] [FAIL] Backup process died while waiting for ready")
                return
            if not self._is_port_free(self.backup_state_port):
                elapsed = time.time() - t0
                print(
                    f"[AUTO_SPAWNER] [OK] Backup state-receiver ready on port "
                    f"{self.backup_state_port} (took {elapsed:.1f}s)"
                )
                return
            time.sleep(0.5)
        print(
            f"[AUTO_SPAWNER] [FAIL] Backup never opened port {self.backup_state_port} "
            f"within {timeout}s"
        )

    def _monitor_backup(self):
        """Restart the backup if it dies unexpectedly (unless explicitly stopped)."""
        while self._respawn_enabled:
            time.sleep(2.0)
            if not self._respawn_enabled:
                break
            if self.backup_process and self.backup_process.poll() is not None:
                print("[AUTO_SPAWNER] Backup process died -- respawning...")
                time.sleep(1.0)
                if self._respawn_enabled:
                    self._do_spawn()
                break

    @staticmethod
    def _is_port_free(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))
                return True
        except OSError:
            return False
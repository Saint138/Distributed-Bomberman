
import json
import os
import random
import socket
import sys
import threading
import time
import uuid
from typing import Optional

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", ".."))
_src  = os.path.join(_root, "src")
for _p in (_root, _src):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from server.services.game_service import GameService
from server.controller.command_controller import CommandController
from server.network.server_network import ClientHandler, send_state_to_clients
from common.constants import (
    PRIMARY_GAME_PORT,
    BACKUP_STATE_PORT,
    PRIMARY_HEARTBEAT_PORT,
    DEFAULT_PORT,
    MAX_PLAYERS,
)

try:
    from server.fault_tolerance.primary_server import PrimaryServer
    from server.fault_tolerance.backup_server import BackupServer
    from server.fault_tolerance.auto_spawner import AutoSpawner
    FAULT_TOLERANCE_AVAILABLE = True
except ImportError as _ft_err:
    FAULT_TOLERANCE_AVAILABLE = False
    print(f"[WARNING] Fault tolerance unavailable: {_ft_err}")


class BombermanServer:
    """
    Main server class.  Responsibilities:
    * TCP accept loop (fresh joins + RECONNECT post-failover)
    * Per-client handler threads with automatic cleanup
    * Game loop (tick every 100 ms + broadcast state)
    * Fault-tolerance orchestration (primary / backup modes)
    """

    RANDOM_NAMES = [
        "Joel", "Gino", "Magnini", "Omicini", "Yellowstone", "JekFosk",
        "MircMirquez", "Pisons", "Santos30L", "Veri", "Chiara", "Mati",
        "Souzuy", "Foschi", "Akela", "Ronaldo", "Dimarco", "Orsolini",
        "Gaiuzz", "Svilar", "Mcfratm", "Crescione",
    ]

    def __init__(
        self,
        host: str = "localhost",
        port: int = PRIMARY_GAME_PORT,
        mode: str = "auto",
        primary_addr: Optional[str] = None,
        promoted_port: Optional[int] = None,
        enable_fault_tolerance: bool = True,
    ):
        """
        Args:
            host                 : bind address
            port                 : game port this instance listens on
                                   (primary default = PRIMARY_GAME_PORT = 5556)
            mode                 : "auto" (primary+backup) | "backup" | "standalone"
            primary_addr         : "host:port" of primary, only for backup mode
            promoted_port        : port to re-open on after promotion
                                   (must equal PRIMARY_GAME_PORT so proxy still works)
            enable_fault_tolerance: False -> standalone mode
        """
        self.host = host
        self.port = port
        self.mode = mode
        self.promoted_port = promoted_port if promoted_port is not None else port
        self.enable_fault_tolerance = enable_fault_tolerance and FAULT_TOLERANCE_AVAILABLE

        self.game_service = GameService()
        self.player_slots = [False] * MAX_PLAYERS
        self.command_controller = CommandController(self.game_service, self.player_slots)

        self.clients: list = []
        self.spectator_clients: list = []

        self.primary_manager: Optional[PrimaryServer] = None
        self.backup_manager: Optional[BackupServer] = None
        self.auto_spawner: Optional[AutoSpawner] = None

        
        self.reconnect_registry: dict = {}
        self.reconnect_lock = threading.Lock()
        self._server_sock: Optional[socket.socket] = None

       
        if self.enable_fault_tolerance:
            if mode in ("auto", "primary"):
                self._setup_as_primary()
            elif mode == "backup" and primary_addr:
                self._setup_as_backup(primary_addr)
        else:
            print("[SERVER] Standalone mode (no fault tolerance)")
            self.mode = "standalone"

    def _setup_as_primary(self):
        """Spawn a backup process and start heartbeat responder + replication."""
        print("=" * 70)
        print(f"[PRIMARY] Starting as PRIMARY on port {self.port}")
        print("=" * 70)

        self.auto_spawner = AutoSpawner(primary_game_port=self.port)
        backup_state_port = self.auto_spawner.spawn_backup_server()

        if backup_state_port:
            self.primary_manager = PrimaryServer(
                game_service=self.game_service,
                backup_state_ports=[("localhost", backup_state_port)],
                heartbeat_port=self.port + 9,   
                replication_interval=0.1,
            )
            self.primary_manager.start()
            print(f"[PRIMARY] Replicating state to backup on port {backup_state_port}")
        else:
            print("[PRIMARY] [WARN] Could not spawn backup -- running without replication")

    def _setup_as_backup(self, primary_addr: str):
        """Start BackupServer that monitors the primary and promotes on failure."""
        print("=" * 70)
        print(f"[BACKUP] Starting as BACKUP on port {self.port}")
        print(f"[BACKUP] Monitoring primary at {primary_addr}")
        print(f"[BACKUP] Will promote to port {self.promoted_port}")
        print("=" * 70)

        parts = primary_addr.split(":")
        p_host = parts[0]
        p_port = int(parts[1]) if len(parts) > 1 else PRIMARY_GAME_PORT

        self.backup_manager = BackupServer(
            primary_host=p_host,
            primary_heartbeat_port=p_port + 9,   # 5565
            state_port=p_port + 1,                # 5557
            promoted_game_port=self.promoted_port,
            on_promotion=self._on_promotion,
        )
        self.backup_manager.start()

    def _on_promotion(self, replicated_state):
        """
        Called by BackupServer when the primary is declared dead.

        1. Restore replicated game state (if available).
        2. Rebuild reconnect_registry so clients can re-attach.
        3. Switch self.port to promoted_port (= PRIMARY_GAME_PORT).
        4. Become the new primary (spawn backup + start replication).
        5. Open TCP accept socket on promoted_port in a new thread.
        """
        print("[PROMOTION] Taking over as PRIMARY...")

        if replicated_state:
            self.game_service.state = replicated_state

            self.player_slots = [False] * MAX_PLAYERS
            for slot in replicated_state.players:
                if 0 <= slot < MAX_PLAYERS:
                    self.player_slots[slot] = True

            self.command_controller = CommandController(
                self.game_service, self.player_slots
            )

            with self.reconnect_lock:
                self.reconnect_registry.clear()
                for slot, player in replicated_state.players.items():
                    sid = getattr(player, "original_client_id", None)
                    if sid:
                        self.reconnect_registry[sid] = {
                            "player_id": slot,
                            "name": getattr(player, "name", f"Player{slot}"),
                            "is_spectator": False,
                        }
                for spec_id, spec_data in replicated_state.spectators.items():
                    sid = spec_data.get("original_client_id")
                    if sid:
                        self.reconnect_registry[sid] = {
                            "player_id": spec_id,
                            "name": spec_data.get("name", f"Spectator{spec_id}"),
                            "is_spectator": True,
                        }

            print(
                f"[PROMOTION] State restored: "
                f"game={replicated_state.game_state}  "
                f"players={list(replicated_state.players.keys())}  "
                f"reconnect_entries={len(self.reconnect_registry)}"
            )
        else:
            print("[PROMOTION] No replicated state -- starting fresh")
        self.port = self.promoted_port
        self.mode = "primary"
        self._setup_as_primary()

        
        threading.Thread(
            target=self._accept_loop,
            daemon=False,
            name="accept-loop-promoted",
        ).start()

        print(f"[PROMOTION] [OK] Now serving as PRIMARY on port {self.port}")

    def start(self):
        """Start game loop (daemon thread) then run accept loop (blocking)."""
        threading.Thread(
            target=self._game_loop, daemon=True, name="game-loop"
        ).start()
        self._accept_loop()

    def _accept_loop(self):
        """Open (or reopen) server socket and accept incoming connections."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen()
            self._server_sock = srv

            print(f"[SERVER] Listening on {self.host}:{self.port}  mode={self.mode.upper()}")
            print(
                f"[SERVER] Fault tolerance: "
                f"{'ENABLED' if self.enable_fault_tolerance else 'DISABLED'}"
            )
            print("=" * 70)

            while True:
                try:
                    conn, addr = srv.accept()
                    threading.Thread(
                        target=self._handle_new_connection,
                        args=(conn, addr),
                        daemon=True,
                    ).start()
                except OSError:
                    break
                except Exception as exc:
                    print(f"[SERVER] Accept error: {exc}")

        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            self._shutdown()
        except Exception as exc:
            print(f"[SERVER] Fatal accept error: {exc}")
            import traceback
            traceback.print_exc()

    def _shutdown(self):
        if self.auto_spawner:
            self.auto_spawner.stop_backup()
        if self.primary_manager:
            self.primary_manager.stop()
        if self.backup_manager:
            self.backup_manager.stop()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def _game_loop(self):
        cleanup_ticker = 0
        while True:
            self.game_service.tick()
            cleanup_ticker += 1
            if cleanup_ticker >= 50:
                self.game_service.cleanup_client_mappings()
                cleanup_ticker = 0
            state = self.game_service.get_state()
            send_state_to_clients(self.clients, self.spectator_clients, state)
            time.sleep(0.1)

    def _handle_new_connection(self, conn: socket.socket, addr: tuple):
        """Dispatch: RECONNECT handshake (post-failover) or fresh join."""
        try:
            conn.settimeout(2.0)
            try:
                raw = conn.recv(4096).decode("utf-8", errors="replace").strip()
            except socket.timeout:
                raw = ""
            finally:
                conn.settimeout(None)

            if raw.startswith("RECONNECT:"):
                self._handle_reconnect(conn, addr, raw)
            else:
                self._handle_fresh_join(conn, addr)

        except (OSError, socket.error) as exc:
            print(f"[SERVER] Network error for {addr}: {exc}")
            self._safe_close(conn)
        except Exception as exc:
            print(f"[SERVER] Error for {addr}: {exc}")
            self._safe_close(conn)


    def _handle_reconnect(self, conn: socket.socket, addr: tuple, msg: str):
        parts = msg.split(":", 1)
        if len(parts) < 2:
            print(f"[RECONNECT] Bad format from {addr}: {msg!r}")
            self._handle_fresh_join(conn, addr)
            return
        session_id = parts[1].split("\n")[0].strip()
        print(f"[RECONNECT] {addr}  session_id={session_id}")

        with self.reconnect_lock:
            info = self.reconnect_registry.get(session_id)
            if not info and session_id.startswith("player_"):
                try:
                    target_pid = int(session_id.split("_")[1])
                    for sid, entry in self.reconnect_registry.items():
                        if entry["player_id"] == target_pid and not entry["is_spectator"]:
                            info = entry
                            session_id = sid
                            print(f"[RECONNECT] Fallback match: player_id={target_pid}")
                            break
                except (ValueError, IndexError):
                    pass

        if not info:
            print(f"[RECONNECT] Unknown session {session_id} -- treating as new")
            self._handle_fresh_join(conn, addr)
            return

        pid     = info["player_id"]
        name    = info["name"]
        is_spec = info["is_spectator"]
        print(f"[RECONNECT] [OK] Restoring Player {pid} ({name})  spectator={is_spec}")

        conn.sendall((json.dumps({
            "join_success": True,
            "player_id": pid,
            "is_spectator": is_spec,
            "player_name": name,
            "reconnected": True,
        }) + "\n").encode())

        if is_spec:
            self.spectator_clients.append(conn)
        else:
            if 0 <= pid < MAX_PLAYERS:
                self.player_slots[pid] = True
            self.clients.append(conn)
            if pid not in self.game_service.state.players:
                self.game_service.add_player(pid, name)
                self.game_service.state.players[pid].original_client_id = session_id
                self.game_service.register_client_player(session_id, pid)
                print(f"[RECONNECT] Re-added Player {pid} ({name}) to game state")
        with self.reconnect_lock:
            self.reconnect_registry[session_id] = {
                "player_id": pid,
                "name": name,
                "is_spectator": is_spec,
            }

        handler = ClientHandler(
            conn, addr, self.command_controller, pid, is_spec, name, session_id
        )
        threading.Thread(
            target=self._run_handler, args=(handler, pid, is_spec, session_id), daemon=True
        ).start()

    def _handle_fresh_join(self, conn: socket.socket, addr: tuple):
        name = self._unique_name()
        session_id = f"client_{uuid.uuid4().hex}"

        if self.game_service.state.game_state == "playing":
            self._assign_spectator(conn, addr, name, session_id)
        else:
            slot = self._free_slot()
            if slot is not None:
                self._assign_player(conn, addr, slot, name, session_id)
            else:
                self._assign_spectator(conn, addr, name, session_id, reason="lobby full")

    def _assign_player(self, conn, addr, slot, name, session_id):
        self.player_slots[slot] = True
        self.game_service.add_player(slot, name)
        self.game_service.state.players[slot].original_client_id = session_id
        self.game_service.register_client_player(session_id, slot)
        with self.reconnect_lock:
            self.reconnect_registry[session_id] = {
                "player_id": slot,
                "name": name,
                "is_spectator": False,
            }
        self.clients.append(conn)
        conn.sendall((json.dumps({
            "join_success": True,
            "player_id": slot,
            "is_spectator": False,
            "player_name": name,
            "session_id": session_id,
        }) + "\n").encode())
        handler = ClientHandler(
            conn, addr, self.command_controller, slot, False, name, session_id
        )
        threading.Thread(
            target=self._run_handler, args=(handler, slot, False, session_id), daemon=True
        ).start()
        print(f"[JOIN] {addr} -> Player {slot} ({name})  session={session_id}")

    def _assign_spectator(self, conn, addr, name, session_id, reason="game in progress"):
        sid = self.game_service.add_spectator(name)
        self.game_service.state.spectators[sid]["original_client_id"] = session_id
        with self.reconnect_lock:
            self.reconnect_registry[session_id] = {
                "player_id": sid,
                "name": name,
                "is_spectator": True,
            }
        self.spectator_clients.append(conn)
        conn.sendall((json.dumps({
            "join_success": True,
            "player_id": sid,
            "is_spectator": True,
            "player_name": name,
            "session_id": session_id,
        }) + "\n").encode())
        handler = ClientHandler(
            conn, addr, self.command_controller, sid, True, name, session_id
        )
        threading.Thread(
            target=self._run_handler, args=(handler, sid, True, session_id), daemon=True
        ).start()
        print(f"[JOIN] {addr} -> Spectator {sid} ({name})  [{reason}]  session={session_id}")

    def _run_handler(self, handler: ClientHandler, user_id: int, is_spectator: bool, session_id: str = None):
        """Run ClientHandler; clean up broadcast lists and game state on exit."""
        try:
            handler.handle()
        finally:
            final_id   = handler.user_id
            final_spec = handler.is_spectator

            for lst in (self.clients, self.spectator_clients):
                try:
                    lst.remove(handler.conn)
                except ValueError:
                    pass
            if final_spec or (isinstance(final_id, int) and final_id >= 100):
                try:
                    self.game_service.remove_spectator(final_id)
                except Exception as exc:
                    print(f"[CLEANUP] Spectator remove error: {exc}")
            else:
                try:
                    if 0 <= final_id < MAX_PLAYERS:
                        self.player_slots[final_id] = False
                    self.game_service.handle_player_disconnect(final_id)
                except Exception as exc:
                    print(f"[CLEANUP] Player disconnect error: {exc}")

    def _free_slot(self) -> Optional[int]:
        for i in range(MAX_PLAYERS):
            if not self.player_slots[i] and i not in self.game_service.state.players:
                return i
        return None

    def _unique_name(self) -> str:
        used = {
            p.name
            for p in self.game_service.state.players.values()
            if p.name
        } | {
            s["name"]
            for s in self.game_service.state.spectators.values()
            if s.get("name")
        }
        available = [n for n in self.RANDOM_NAMES if n not in used]
        if available:
            return random.choice(available)
        for _ in range(1000):
            name = f"{random.choice(self.RANDOM_NAMES)}{random.randint(1, 999)}"
            if name not in used:
                return name
        return f"Player{random.randint(1000, 9999)}"

    @staticmethod
    def _safe_close(sock: socket.socket):
        try:
            sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Bomberman Server with automatic fault tolerance"
    )
    parser.add_argument(
        "--mode", choices=["auto", "backup"], default="auto",
        help="auto = primary + auto-spawned backup (default);  backup = manual backup",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument(
        "--port", type=int, default=PRIMARY_GAME_PORT,
        help=f"Game port this instance listens on (default: {PRIMARY_GAME_PORT})",
    )
    parser.add_argument(
        "--primary", type=str, default=None,
        help="Primary address for backup mode  (format: host:port)",
    )
    parser.add_argument(
        "--promoted-port", type=int, default=None,
        help="Port to re-open on after promotion -- must equal primary game port",
    )
    parser.add_argument(
        "--no-ft", action="store_true",
        help="Disable fault tolerance (standalone mode, listens on DEFAULT_PORT)",
    )
    args = parser.parse_args()

    if args.mode == "backup" and not args.primary:
        parser.error("--primary is required in backup mode")
    port = DEFAULT_PORT if args.no_ft else args.port

    server = BombermanServer(
        host=args.host,
        port=port,
        mode=args.mode,
        primary_addr=args.primary,
        promoted_port=args.promoted_port,
        enable_fault_tolerance=not args.no_ft,
    )
    server.start()


if __name__ == "__main__":
    main()
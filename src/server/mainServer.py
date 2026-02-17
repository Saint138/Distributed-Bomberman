"""
Server entry point - Main orchestration with automatic fault tolerance
"""
import socket
import threading
import time
import json
import random
import sys
import os
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.services.game_service import GameService
from server.controller.command_controller import CommandController
from server.network.server_network import ClientHandler, send_state_to_clients

try:
    from server.fault_tolerance.primary_server import PrimaryServer
    from server.fault_tolerance.backup_server import BackupServer
    from server.fault_tolerance.auto_spawner import AutoSpawner
    FAULT_TOLERANCE_AVAILABLE = True
except ImportError:
    FAULT_TOLERANCE_AVAILABLE = False
    print("[WARNING] Fault tolerance components not available")


class BombermanServer:
    """Main server class with automatic fault tolerance"""
    
    def __init__(self, host: str = "localhost", port: int = 5555, 
                 mode: str = "auto", primary_host: str = None,
                 enable_fault_tolerance: bool = True):
        self.host = host
        self.port = port
        self.mode = mode
        self.enable_fault_tolerance = enable_fault_tolerance and FAULT_TOLERANCE_AVAILABLE
        self.max_players = 4
        self.game_service = GameService()
        self.clients = []
        self.spectator_clients = []
        self.player_slots = [False, False, False, False]
        self.command_controller = CommandController(self.game_service, self.player_slots)
        self.random_names = [
            "Joel", "Gino", "Magnini", "Omicini", "Yellowstone", "JekFosk", "MircMirquez",
            "Pisons", "Santos30L", "JoelMaestroDellaDistribuzione", "Veri", "Chiara", "Mati", "Souzuy", "GiacomoMerda",
            "Foschi", "Akela", "Ronaldo", "Dimarco", "Orsolini", "EstoteSocial", "Pioli",
            "Gaiuzz", "Svilar", "Mcfratm", "Crescione", "Ravenna>Rimini"
        ]
        self.primary_manager: Optional[PrimaryServer] = None
        self.backup_manager: Optional[BackupServer] = None
        self.auto_spawner: Optional[AutoSpawner] = None
        self.reconnect_registry = {}
        self.reconnect_lock = threading.Lock()
        if self.enable_fault_tolerance:
            if mode == "auto" or mode == "primary":
                self._setup_as_primary_with_auto_backup()
            elif mode == "backup" and primary_host:
                self._setup_as_backup(primary_host)
        else:
            print("[SERVER] Running in STANDALONE mode (no fault tolerance)")
            self.mode = "standalone"
            
    def _setup_as_primary_with_auto_backup(self):
        """Setup come primary e spawna automaticamente un backup"""
        print("=" * 70)
        print("[PRIMARY] STARTING AS PRIMARY SERVER (with auto-backup)")
        print("=" * 70)
        
        self.auto_spawner = AutoSpawner(base_port=self.port)
        backup_state_port = self.auto_spawner.spawn_backup_server(self.port)
        
        if backup_state_port:
            backup_servers = [("localhost", backup_state_port)]
            
            self.primary_manager = PrimaryServer(
                game_service=self.game_service,
                backup_servers=backup_servers,
                heartbeat_port=self.port + 10,
                replication_interval=0.1 
            )
            self.primary_manager.start()
            print(f"[PRIMARY] Automatic backup configured")
            print(f"[PRIMARY] State replication to port {backup_state_port}")
        else:
            print("[PRIMARY] WARNING: Failed to spawn backup - running without fault tolerance")
            
    def _setup_as_backup(self, primary_host: str):
        """Setup come backup di un primary esistente"""
        print("=" * 70)
        print("[BACKUP] STARTING AS BACKUP SERVER")
        print("=" * 70)
        
        parts = primary_host.split(":")
        p_host = parts[0]
        p_port = int(parts[1]) if len(parts) > 1 else 5555
        
        def on_promotion_callback(replicated_state):
            """Callback chiamata quando il backup diventa primary"""
            print("[CALLBACK] PROMOTION TO PRIMARY - Restoring state...")
            
            if replicated_state:

                self.game_service.state = replicated_state
                self.player_slots = [False, False, False, False]
                for slot in replicated_state.players:
                    if 0 <= slot < 4:
                        self.player_slots[slot] = True
                self.command_controller = CommandController(
                    self.game_service,
                    self.player_slots
                )
                with self.reconnect_lock:
                    self.reconnect_registry.clear()
                    for slot, player in replicated_state.players.items():
                        session_id = getattr(player, 'original_client_id', None)
                        name = getattr(player, 'name', f"Player{slot}")
                        if session_id:
                            self.reconnect_registry[session_id] = {
                                'player_id': slot,
                                'name': name,
                                'is_spectator': False
                            }
                            print(f"[CALLBACK] Registered reconnect for Player {slot} ({name}) session={session_id}")
                    
                    for spec_id, spec_data in replicated_state.spectators.items():
                        session_id = spec_data.get('original_client_id')
                        name = spec_data.get('name', f"Spectator{spec_id}")
                        if session_id:
                            self.reconnect_registry[session_id] = {
                                'player_id': spec_id,
                                'name': name,
                                'is_spectator': True
                            }
                
                print(f"[CALLBACK] State restored: game_state={replicated_state.game_state}")
                print(f"[CALLBACK] Players restored: {list(replicated_state.players.keys())}")
                print(f"[CALLBACK] Reconnect registry: {len(self.reconnect_registry)} entries")
            else:
                print("[CALLBACK] No replicated state - starting fresh")
            
            self.mode = "primary"
            print("[CALLBACK] Spawning new backup server...")
            self._setup_as_primary_with_auto_backup()
            
        self.backup_manager = BackupServer(
            primary_host=p_host,
            primary_port=p_port,
            heartbeat_port=p_port + 10,
            state_port=p_port + 1,
            on_promotion=on_promotion_callback
        )
        self.backup_manager.start()
        print(f"[BACKUP] Monitoring primary at {p_host}:{p_port + 10}")
        print(f"[BACKUP] State receiver on port {p_port + 1}")

    def generate_unique_name(self) -> str:
        """Generates a unique name not already in use"""
        used_names = set()
        for player in self.game_service.state.players.values():
            if hasattr(player, 'name') and player.name:
                used_names.add(player.name)
        for spectator in self.game_service.state.spectators.values():
            if spectator.get("name"):
                used_names.add(spectator["name"])
        available = [name for name in self.random_names if name not in used_names]
        if available:
            return random.choice(available)
        for i in range(1, 1000):
            name = f"{random.choice(self.random_names)}{i}"
            if name not in used_names:
                return name
        return f"Player{random.randint(1000, 9999)}"

    def get_free_player_slot(self) -> Optional[int]:
        """Finds a free player slot, returns None if no slots available"""
        for i in range(self.max_players):
            if not self.player_slots[i]:
                if i not in self.game_service.state.players:
                    return i
        return None

    def game_loop(self):
        """Main game loop"""
        cleanup_counter = 0
        while True:
            self.game_service.tick()
            cleanup_counter += 1
            if cleanup_counter >= 50:
                self.game_service.cleanup_client_mappings()
                cleanup_counter = 0
            state = self.game_service.get_state()
            send_state_to_clients(self.clients, self.spectator_clients, state)
            time.sleep(0.1)

    def handle_new_connection(self, conn: socket.socket, addr: tuple):
        """
        Handles a new connection.
        
        Prima controlla se è una riconnessione post-failover (ha un session_id
        nel reconnect_registry). In tal caso ripristina la sessione esistente.
        Altrimenti crea una nuova sessione.
        """
        print(f"[NEW CONNECTION] {addr} connecting...")
        try:
            
            conn.settimeout(2.0)
            try:
                first_data = conn.recv(4096).decode('utf-8', errors='replace').strip()
            except socket.timeout:
                first_data = ""
            finally:
                conn.settimeout(None)
            if first_data.startswith("RECONNECT:"):
                self._handle_reconnect(conn, addr, first_data)
                return
            
            player_name = self.generate_unique_name()
            client_session_id = f"client_{random.randint(10000, 99999)}_{time.time()}"
            print(f"[AUTO-ASSIGN] Generated name: {player_name}, session={client_session_id}")
            
            if self.game_service.state.game_state == "playing":
                self._assign_as_spectator(conn, addr, player_name, client_session_id)
            else:
                free_slot = self.get_free_player_slot()
                if free_slot is not None:
                    self._assign_as_player(conn, addr, free_slot, player_name, client_session_id)
                else:
                    self._assign_as_spectator(conn, addr, player_name, client_session_id, reason="lobby full")
                    
        except (socket.error, OSError) as e:
            print(f"[ERROR] Network error handling connection from {addr}: {e}")
            self._safe_close_connection(conn)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[ERROR] Data error handling connection from {addr}: {e}")
            self._safe_close_connection(conn)
        except KeyError as e:
            print(f"[ERROR] Missing data handling connection from {addr}: {e}")
            self._safe_close_connection(conn)

    def _handle_reconnect(self, conn: socket.socket, addr: tuple, reconnect_msg: str):
        """
        Gestisce una riconnessione post-failover.
        
        Formato messaggio: RECONNECT:<session_id>
        
        Se session_id è nel registry, ripristina la sessione esistente.
        Se session_id è "player_X" (fallback del proxy), cerca per player_id.
        Altrimenti tratta come nuova connessione.
        """
        try:
            parts = reconnect_msg.split(":", 1)
            if len(parts) < 2:
                print(f"[RECONNECT] Invalid format from {addr}: {reconnect_msg}")
                self._handle_as_new(conn, addr)
                return
            
            session_id = parts[1].strip()
            print(f"[RECONNECT] Request from {addr} with session={session_id}")
            
            with self.reconnect_lock:
                session_info = self.reconnect_registry.get(session_id)
    
                if not session_info and session_id.startswith("player_"):
                    try:
                        player_id = int(session_id.split("_")[1])
                        for sid, info in self.reconnect_registry.items():
                            if info['player_id'] == player_id and not info['is_spectator']:
                                session_info = info
                                session_id = sid
                                print(f"[RECONNECT] Found via player_id fallback: player={player_id}")
                                break
                    except (ValueError, IndexError):
                        pass
            
            if session_info:
                player_id = session_info['player_id']
                name = session_info['name']
                is_spectator = session_info['is_spectator']
                
                print(f"[RECONNECT] ✅ Restoring session: Player {player_id} ({name}), spectator={is_spectator}")
                
                response = json.dumps({
                    "join_success": True,
                    "player_id": player_id,
                    "is_spectator": is_spectator,
                    "player_name": name,
                    "reconnected": True 
                })
                conn.sendall((response + "\n").encode())
                
                if is_spectator:
                    self.spectator_clients.append(conn)
                    handler = ClientHandler(conn, addr, self.command_controller, player_id, True, name, session_id)
                    thread = threading.Thread(
                        target=self._run_handler_with_cleanup,
                        args=(handler, player_id, True),
                        daemon=True
                    )
                else:
                    if 0 <= player_id < 4:
                        self.player_slots[player_id] = True
                    self.clients.append(conn)
                    handler = ClientHandler(conn, addr, self.command_controller, player_id, False, name, session_id)
                    thread = threading.Thread(
                        target=self._run_handler_with_cleanup,
                        args=(handler, player_id, False),
                        daemon=True
                    )
                
                thread.start()
                with self.reconnect_lock:
                    self.reconnect_registry.pop(session_id, None)
                    
            else:
                print(f"[RECONNECT] Unknown session {session_id} - treating as new connection")
                self._handle_as_new(conn, addr)
                
        except Exception as e:
            print(f"[RECONNECT] Error: {e}")
            import traceback
            traceback.print_exc()
            self._handle_as_new(conn, addr)
    
    def _handle_as_new(self, conn: socket.socket, addr: tuple):
        """Tratta la connessione come nuova (nessuna sessione da ripristinare)"""
        player_name = self.generate_unique_name()
        client_session_id = f"client_{random.randint(10000, 99999)}_{time.time()}"
        
        if self.game_service.state.game_state == "playing":
            self._assign_as_spectator(conn, addr, player_name, client_session_id)
        else:
            free_slot = self.get_free_player_slot()
            if free_slot is not None:
                self._assign_as_player(conn, addr, free_slot, player_name, client_session_id)
            else:
                self._assign_as_spectator(conn, addr, player_name, client_session_id, reason="lobby full")

    @staticmethod
    def _safe_close_connection(conn: socket.socket):
        """Safely closes a socket connection"""
        try:
            conn.close()
        except (socket.error, OSError):
            pass

    def _assign_as_player(self, conn: socket.socket, addr: tuple, slot: int, name: str, session_id: str):
        """Assigns a connection as a player"""
        self.player_slots[slot] = True
        self.game_service.add_player(slot, name)
        self.game_service.state.players[slot].original_client_id = session_id
        self.game_service.register_client_player(session_id, slot)
        self.clients.append(conn)
        response = json.dumps({
            "join_success": True,
            "player_id": slot,
            "is_spectator": False,
            "player_name": name,
            "session_id": session_id   
        })
        conn.sendall((response + "\n").encode())
        handler = ClientHandler(conn, addr, self.command_controller, slot, False, name, session_id)
        thread = threading.Thread(target=self._run_handler_with_cleanup, args=(handler, slot, False), daemon=True)
        thread.start()
        print(f"[PLAYER] {addr} -> Player {slot} ({name})")

    def _assign_as_spectator(self, conn: socket.socket, addr: tuple, name: str, session_id: str, reason: str = "game in progress"):
        """Assigns a connection as a spectator"""
        spectator_id = self.game_service.add_spectator(name)
        self.spectator_clients.append(conn)
        response = json.dumps({
            "join_success": True,
            "player_id": spectator_id,
            "is_spectator": True,
            "player_name": name,
            "session_id": session_id   
        })
        conn.sendall((response + "\n").encode())
        handler = ClientHandler(conn, addr, self.command_controller, spectator_id, True, name, session_id)
        thread = threading.Thread(target=self._run_handler_with_cleanup, args=(handler, spectator_id, True), daemon=True)
        thread.start()
        print(f"[SPECTATOR] {addr} -> Spectator {spectator_id} ({name}) - {reason}")

    def _run_handler_with_cleanup(self, handler: ClientHandler, user_id: int, is_spectator: bool):
        """Runs handler with automatic cleanup on disconnect"""
        try:
            handler.handle()
        finally:
            final_user_id = handler.user_id
            final_is_spectator = handler.is_spectator
            print(f"[CLEANUP] Cleaning up: original_id={user_id}, final_id={final_user_id}, "
                  f"original_spectator={is_spectator}, final_spectator={final_is_spectator}")
            
            if handler.conn in self.clients:
                try:
                    self.clients.remove(handler.conn)
                except ValueError:
                    pass
            if handler.conn in self.spectator_clients:
                try:
                    self.spectator_clients.remove(handler.conn)
                except ValueError:
                    pass
            
            if final_is_spectator or (isinstance(final_user_id, int) and final_user_id >= 100):
                try:
                    print(f"[CLEANUP] Removing spectator {final_user_id}")
                    self.game_service.remove_spectator(final_user_id)
                except (KeyError, AttributeError) as e:
                    print(f"[CLEANUP] Spectator remove error: {e}")
            else:
                try:
                    if 0 <= final_user_id < 4:
                        self.player_slots[final_user_id] = False
                        print(f"[CLEANUP] Freed player slot {final_user_id}")
                    print(f"[CLEANUP] Disconnecting player {final_user_id}")
                    self.game_service.handle_player_disconnect(final_user_id)
                except (KeyError, AttributeError, IndexError) as e:
                    print(f"[CLEANUP] Player disconnect error: {e}")

    def start(self):
        """Starts the server"""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen()
        
        print(f"[SERVER] Listening on {self.host}:{self.port}")
        print(f"[SERVER] Mode: {self.mode.upper()}")
        if self.enable_fault_tolerance:
            print(f"[SERVER] Fault Tolerance: ENABLED")
        else:
            print(f"[SERVER] Fault Tolerance: DISABLED")
        print("=" * 70)
        
        threading.Thread(target=self.game_loop, daemon=True).start()
        
        try:
            while True:
                conn, addr = srv.accept()
                self.handle_new_connection(conn, addr)
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            if self.auto_spawner:
                self.auto_spawner.stop_backup()
            if self.primary_manager:
                self.primary_manager.stop()
            if self.backup_manager:
                self.backup_manager.stop()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bomberman Server (with automatic fault tolerance)')
    parser.add_argument('--mode', choices=['auto', 'backup'], default='auto',
                        help='Server mode: auto=primary with auto-backup (default), backup=manual backup')
    parser.add_argument('--host', default='localhost',
                        help='Host address (default: localhost)')
    parser.add_argument('--port', type=int, default=5555,
                        help='Main game port (default: 5555)')
    parser.add_argument('--primary', type=str,
                        help='Primary server address for manual backup mode (format: host:port)')
    parser.add_argument('--no-ft', action='store_true',
                        help='Disable fault tolerance (run standalone)')
    
    args = parser.parse_args()
    
    if args.mode == 'backup' and not args.primary:
        parser.error("--primary is required when mode is 'backup'")
    
    if args.mode == 'backup':
        server = BombermanServer(
            host=args.host,
            port=args.port,
            mode='backup',
            primary_host=args.primary,
            enable_fault_tolerance=not args.no_ft
        )
    else:
        server = BombermanServer(
            host=args.host,
            port=args.port,
            mode='auto',
            enable_fault_tolerance=not args.no_ft
        )
    
    server.start()


if __name__ == "__main__":
    main()
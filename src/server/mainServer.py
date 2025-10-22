"""
Server entry point - Main orchestration
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

class BombermanServer:
    """Main server class"""
    def __init__(self, host: str = "localhost", port: int = 5555):
        self.host = host
        self.port = port
        self.max_players = 4
        self.game_service = GameService()
        self.clients = []
        self.spectator_clients = []
        self.player_slots = [False, False, False, False]
        self.command_controller = CommandController(self.game_service, self.player_slots)
        self.random_names = [
            "Bomber", "Blaster", "Dynamite", "Thunder", "Flash", "Storm", "Phoenix",
            "Shadow", "Viper", "Rocket", "Ninja", "Falcon", "Tiger", "Wolf", "Eagle",
            "Hunter", "Warrior", "Knight", "Ranger", "Scout", "Sniper", "Ghost",
            "Phantom", "Mystic", "Raven", "Hawk", "Dragon", "Cobra", "Panther", "Lion",
            "Ace", "Blade", "Cyber", "Echo", "Frost", "Grim", "Hero", "Iron", "Jade",
            "King", "Legend", "Master", "Nova", "Onyx", "Prime", "Quest", "Rebel",
            "Spike", "Titan", "Ultra", "Vector", "Wild", "Xenon", "Yell", "Zero"
        ]

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
        """Handles a new connection"""
        print(f"[NEW CONNECTION] {addr} connecting...")
        try:
            player_name = self.generate_unique_name()
            client_session_id = f"client_{random.randint(10000, 99999)}_{time.time()}"
            print(f"[AUTO-ASSIGN] Generated name: {player_name}")
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
            "player_name": name
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
            "player_name": name
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
        threading.Thread(target=self.game_loop, daemon=True).start()
        while True:
            conn, addr = srv.accept()
            self.handle_new_connection(conn, addr)

def main():
    """Entry point"""
    server = BombermanServer(host="localhost", port=5555)
    server.start()

if __name__ == "__main__":
    main()
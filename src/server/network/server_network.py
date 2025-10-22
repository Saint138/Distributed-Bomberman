"""
Server-side network management
"""
import socket
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.controller.command_controller import CommandController

class ClientHandler:
    """Handles communication with a single client"""
    def __init__(self, conn: socket.socket, addr: tuple, command_controller: CommandController,
                 user_id: int, is_spectator: bool, player_name: str, client_id: str):
        self.conn = conn
        self.addr = addr
        self.controller = command_controller
        self.user_id = user_id
        self.is_spectator = is_spectator
        self.player_name = player_name
        self.client_id = client_id
        self.user_type = "Spectator" if is_spectator else "Player"
        self.display_name = player_name or f"{self.user_type} {user_id}"

    def handle(self):
        """Main client handling loop"""
        print(f"[HANDLER] Starting {self.user_type} {self.user_id} ({self.display_name}) from {self.addr}")
        try:
            while True:
                data = self.conn.recv(1024)
                if not data:
                    break
                try:
                    message = data.decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue
                if not message:
                    continue
                response = self.controller.handle_command(message, self.user_id, self.is_spectator, self.player_name)
                if response.get("type") == "pong":
                    self.conn.sendall(b"PONG\n")
                elif response.get("type") == "conversion":
                    if response.get("success"):
                        old_user_id = self.user_id
                        self.user_id = response["new_player_id"]
                        self.is_spectator = False
                        self.user_type = "Player"
                        print(f"[HANDLER] Spectator {old_user_id} converted to Player {self.user_id}")
                        resp_json = json.dumps({
                            "conversion_success": True,
                            "new_player_id": self.user_id,
                            "is_spectator": False
                        })
                        self.conn.sendall((resp_json + "\n").encode())
                    else:
                        self.conn.sendall(b'{"conversion_success": false}\n')
        except ConnectionResetError:
            pass
        except (OSError, ConnectionError, BrokenPipeError) as e:
            print(f"[HANDLER] Error: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        """Cleanup when client disconnects"""
        print(f"[HANDLER] Disconnecting {self.user_type} {self.user_id} ({self.display_name}) from {self.addr}")
        try:
            self.conn.close()
        except (OSError, AttributeError):
            pass

def send_state_to_clients(clients: list, spectators: list, state: dict):
    """Sends game state to all connected clients"""
    state_json = json.dumps(state) + "\n"
    for client in list(clients):
        try:
            client.sendall(state_json.encode())
        except (OSError, ConnectionError, BrokenPipeError, AttributeError):
            try:
                clients.remove(client)
            except ValueError:
                pass
    for spectator in list(spectators):
        try:
            spectator.sendall(state_json.encode())
        except (OSError, ConnectionError, BrokenPipeError, AttributeError):
            try:
                spectators.remove(spectator)
            except ValueError:
                pass
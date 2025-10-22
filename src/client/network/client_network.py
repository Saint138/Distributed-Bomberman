"""
Network communication management for the client
"""
import socket
import threading
import json
from typing import Callable, Optional

class NetworkManager:
    """Manages TCP connection with the server"""
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.running = True
        self.on_state_update: Optional[Callable] = None
        self.on_join_success: Optional[Callable] = None
        self.on_conversion: Optional[Callable] = None

    def start_receiving(self) -> None:
        """Starts the receiving thread"""
        thread = threading.Thread(target=self._receive_loop, daemon=True)
        thread.start()

    def send_command(self, command: str) -> None:
        """Sends a command to the server"""
        try:
            self.sock.sendall(command.encode('utf-8'))
        except (OSError, ConnectionError, BrokenPipeError) as e:
            print(f"[NETWORK] Error sending command: {e}")

    def _receive_loop(self) -> None:
        """Message receiving loop from server"""
        buffer = ""
        while self.running:
            try:
                data = self.sock.recv(8192).decode()
                if not data:
                    print("[NETWORK] Connection closed by server")
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    self._handle_message(line)
            except (OSError, ConnectionError, ConnectionResetError, BrokenPipeError) as e:
                print(f"[NETWORK] Error receiving state: {e}")
                break
            except UnicodeDecodeError as e:
                print(f"[NETWORK] Decode error: {e}")
                continue

    def _handle_message(self, message: str) -> None:
        """Handles a message received from the server"""
        try:
            response = json.loads(message)
            if "join_success" in response and response["join_success"]:
                if self.on_join_success:
                    self.on_join_success(
                        response["player_id"],
                        response.get("is_spectator", False),
                        response.get("player_name", "")
                    )
                return
            if "conversion_success" in response and response["conversion_success"]:
                if self.on_conversion:
                    self.on_conversion(
                        response["new_player_id"],
                        response.get("is_spectator", False)
                    )
                return
            if self.on_state_update:
                self.on_state_update(response)
        except json.JSONDecodeError as e:
            print(f"[NETWORK] JSON decode error: {e}")
        except (KeyError, TypeError, ValueError) as e:
            print(f"[NETWORK] Error handling message: {e}")

    def stop(self) -> None:
        """Stops the network manager"""
        self.running = False
        try:
            self.sock.close()
        except (OSError, AttributeError):
            pass
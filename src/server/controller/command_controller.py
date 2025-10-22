"""
Controller to handle commands received from clients
"""
import sys
import os

current_file = os.path.abspath(__file__)
controllers_dir = os.path.dirname(current_file)
server_dir = os.path.dirname(controllers_dir)
src_dir = os.path.dirname(server_dir)

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from ..services.game_service import GameService
    from ..models import GAME_STATE_LOBBY, GAME_STATE_PLAYING, GAME_STATE_VICTORY
except ImportError:
    from server.services.game_service import GameService
    from server.models import GAME_STATE_LOBBY, GAME_STATE_PLAYING, GAME_STATE_VICTORY

class CommandController:
    """Controller that translates client commands into game actions"""
    def __init__(self, game_service: GameService, player_slots=None):
        """
        Initializes the controller

        Args:
            game_service: The game service
            player_slots: List of player slots (to manage spectator->player conversions)
        """
        self.game = game_service
        self.player_slots = player_slots

    def handle_command(self, command: str, user_id: int, is_spectator: bool, player_name: str = "") -> dict:
        """
        Handles a command received from a client

        Returns:
            dict with any special responses
        """
        if not command:
            return {}
        if command == "PING":
            return {"type": "pong"}
        command_upper = command.upper()
        if is_spectator:
            return self._handle_spectator_command(command, command_upper, user_id, player_name)
        return self._handle_player_command(command, command_upper, user_id, player_name)

    def _handle_spectator_command(self, command: str, command_upper: str, user_id: int, player_name: str) -> dict:
        """Handles spectator commands"""
        if command.startswith("CHAT:"):
            chat_message = command[5:]
            if chat_message.strip():
                self.game.add_chat_message(user_id, chat_message)
            return {}
        if command_upper == "JOIN_GAME":
            if self.game.state.game_state == GAME_STATE_LOBBY:
                spec_name = player_name or f"Spectator {user_id}"
                new_pid = self.game.convert_spectator_to_player(user_id, spec_name)
                if new_pid >= 0:
                    print(f"[CONVERT] Spectator {user_id} -> Player {new_pid}")
                    if self.player_slots is not None and 0 <= new_pid < 4:
                        self.player_slots[new_pid] = True
                        print(f"[CONVERT] Allocated player slot {new_pid}")
                    return {
                        "type": "conversion",
                        "success": True,
                        "new_player_id": new_pid
                    }
                else:
                    return {
                        "type": "conversion",
                        "success": False
                    }
        return {}

    def _handle_player_command(self, command: str, command_upper: str, user_id: int, player_name: str) -> dict:
        """Handles player commands"""
        if command_upper in ("UP", "DOWN", "LEFT", "RIGHT"):
            self.game.move_player(user_id, command_upper)
            return {}
        if command_upper == "BOMB":
            self.game.place_bomb(user_id)
            return {}
        if command_upper == "START_GAME":
            if (self.game.state.game_state == GAME_STATE_LOBBY and
                    user_id == self.game.get_current_host()):
                if self.game.start_game():
                    print(f"[GAME] Player {user_id} ({player_name}) started the game")
            return {}
        if command_upper == "PLAY_AGAIN":
            if self.game.state.game_state == GAME_STATE_VICTORY:
                self.game.return_to_lobby()
            return {}
        if command.startswith("CHAT:"):
            chat_message = command[5:]
            if chat_message.strip():
                self.game.add_chat_message(user_id, chat_message)
        return {}
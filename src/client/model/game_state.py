"""
Model for game state on the client side
"""
from typing import Optional, Dict, Any

class GameState:
    """Represents the complete game state"""
    def __init__(self):
        self.state: Optional[Dict[str, Any]] = None
        self.player_id: Optional[int] = None
        self.is_spectator: bool = False
        self.player_name: str = ""
        self.current_screen: str = "connecting"

    def update(self, new_state: Dict[str, Any]) -> None:
        """Updates state with data from server"""
        self.state = new_state
        if self.state:
            game_state = self.state.get("game_state")
            if game_state == "lobby":
                self.current_screen = "lobby"
            elif game_state == "playing":
                self.current_screen = "game"
            elif game_state == "victory":
                self.current_screen = "victory"

    def set_player_info(self, player_id: int, is_spectator: bool, name: str) -> None:
        """Sets local player information"""
        self.player_id = player_id
        self.is_spectator = is_spectator
        self.player_name = name
        self.current_screen = "lobby"

    def get_game_state(self) -> str:
        """Returns current game state"""
        return self.state.get("game_state") if self.state else "lobby"

    def get_players(self) -> Dict:
        """Returns players"""
        return self.state.get("players", {}) if self.state else {}

    def get_spectators(self) -> Dict:
        """Returns spectators"""
        return self.state.get("spectators", {}) if self.state else {}

    def get_chat_messages(self) -> list:
        """Returns chat messages"""
        return self.state.get("chat_messages", []) if self.state else []

    def get_current_host(self) -> int:
        """Returns current host ID"""
        return self.state.get("current_host_id", 0) if self.state else 0

    def can_start_game(self) -> bool:
        """Checks if game can be started"""
        return self.state.get("can_start", False) if self.state else False

    def get_map(self) -> list:
        """Returns game map"""
        return self.state.get("map", []) if self.state else []

    def get_bombs(self) -> list:
        """Returns active bombs"""
        return self.state.get("bombs", []) if self.state else []

    def get_explosions(self) -> list:
        """Returns active explosions"""
        return self.state.get("explosions", []) if self.state else []

    def get_winner_id(self) -> Optional[int]:
        """Returns winner ID"""
        return self.state.get("winner_id") if self.state else None

    def get_victory_timer(self) -> int:
        """Returns victory timer"""
        return self.state.get("victory_timer", 0) if self.state else 0

    def is_host(self) -> bool:
        """Checks if local player is the host"""
        return self.player_id == self.get_current_host() and not self.is_spectator

    def connected_players_count(self) -> int:
        """Counts connected players"""
        if not self.state:
            return 0
        return sum(1 for p in self.get_players().values() if not p.get("disconnected", False))
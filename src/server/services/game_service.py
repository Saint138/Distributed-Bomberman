"""
Service layer for game business logic
Combines and orchestrates functions from core.py
"""
from typing import Any, Dict, Optional
import sys
import os
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(server_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from server.models import (
    State,
    GAME_STATE_LOBBY,
    GAME_STATE_PLAYING,
    GAME_STATE_VICTORY,
    BLOCK_REGEN_MIN_TIME,
    BLOCK_REGEN_MAX_TIME
)
from server import core

class GameService:
    """Service containing all game business logic"""
    def __init__(self):
        self.state = State()

    def add_player(self, player_id: int, name: str = "") -> None:
        """Adds a new player"""
        display_name = name or f"Player {player_id}"
        core.add_player(self.state, player_id, display_name)
        if core.connected_players_count(self.state) == 1:
            self.state.current_host_id = player_id
            self._add_system_message(f"{display_name} is the host")
        self._add_system_message(f"{display_name} joined the lobby")

    def handle_player_disconnect(self, player_id: int) -> None:
        """Handles player disconnection"""
        player = self.state.players.get(player_id)
        if not player:
            return
        player_name = player.name or f"Player {player_id}"
        print(f"[DISCONNECT] {player_name} disconnected")
        if self.state.game_state == GAME_STATE_LOBBY:
            if player_id in self.state.players:
                del self.state.players[player_id]
            stale = [cid for cid, pid in list(self.state.client_player_mapping.items()) if pid == player_id]
            for cid in stale:
                del self.state.client_player_mapping[cid]
            self._add_system_message(f"{player_name} left the lobby")
            if player_id == self.state.current_host_id:
                self.get_current_host()
        elif self.state.game_state == GAME_STATE_PLAYING:
            player.disconnected = True
            player.alive = False
            self._add_system_message(f"{player_name} disconnected")
            self.check_victory()

    def add_spectator(self, name: str = "") -> int:
        """Adds a new spectator"""
        sid = self.state.next_spectator_id
        self.state.next_spectator_id += 1
        display_name = name or f"Spectator {sid}"
        self.state.spectators[sid] = {
            "connected": True,
            "join_time": self.state.now(),
            "name": display_name
        }
        print(f"[SPECTATOR] Spectator {sid} ({display_name}) joined")
        self._add_system_message(f"{display_name} joined as spectator")
        return sid

    def remove_spectator(self, sid: int) -> None:
        """Removes a spectator"""
        if sid in self.state.spectators:
            name = self.state.spectators[sid].get("name", f"Spectator {sid}")
            del self.state.spectators[sid]
            print(f"[SPECTATOR] Spectator {sid} ({name}) left")
            self._add_system_message(f"{name} left")

    def convert_spectator_to_player(self, spectator_id: int, spectator_name: str = "") -> int:
        """Converts a spectator to a player"""
        if spectator_id not in self.state.spectators:
            return -1
        new_pid = self._find_free_player_slot()
        if new_pid is None:
            return -1
        name = self.state.spectators[spectator_id].get("name", spectator_name or f"Player {new_pid}")
        del self.state.spectators[spectator_id]
        self.add_player(new_pid, name)
        self._add_system_message(f"{name} joined as Player {new_pid}")
        return new_pid

    def _find_free_player_slot(self) -> Optional[int]:
        """Finds a free player slot (0-3) or returns None if all slots are full"""
        for i in range(4):
            if i not in self.state.players:
                return i
        return None

    def get_current_host(self) -> int:
        """Gets the current host ID"""
        return core.get_current_host(self.state)

    def start_game(self) -> bool:
        """Starts the game"""
        ok = core.start_game(self.state)
        if ok:
            self._add_system_message("Game started! Good luck!")
        return ok

    def return_to_lobby(self) -> None:
        """Returns to lobby"""
        core.return_to_lobby(self.state)
        self._add_system_message("Returned to lobby. Ready for a new game!")

    def check_victory(self) -> bool:
        """Checks if there's a winner"""
        has_winner = core.check_victory(self.state)
        if has_winner:
            if self.state.winner_id == -1:
                self._add_system_message("Draw - no winners!")
            else:
                winner_name = self.state.players[self.state.winner_id].name \
                    if self.state.winner_id in self.state.players \
                    else f"Player {self.state.winner_id}"
                self._add_system_message(f"{winner_name} wins the game!")
        return has_winner

    def move_player(self, player_id: int, direction: str) -> None:
        """Moves a player"""
        core.move_player(self.state, player_id, direction)

    def place_bomb(self, player_id: int) -> None:
        """Places a bomb"""
        core.place_bomb(self.state, player_id)

    def add_chat_message(self, sender_id: int, message: str, is_system: bool = False) -> None:
        """Adds a chat message"""
        core.add_chat(self.state, sender_id, message, is_system=is_system)

    def _add_system_message(self, message: str) -> None:
        """Adds a system message"""
        self.add_chat_message(-1, message, is_system=True)

    def tick(self) -> None:
        """Updates game state (called every frame)"""
        if self.state.game_state == GAME_STATE_VICTORY:
            self.state.victory_timer -= 1
            if self.state.victory_timer <= 0:
                self.return_to_lobby()
            return
        if self.state.game_state != GAME_STATE_PLAYING:
            return
        for bomb in list(self.state.bombs):
            bomb.timer -= 1
            if bomb.timer <= 0:
                core.explode_bomb(self.state, bomb)
                self.state.bombs.remove(bomb)
        for explosion in list(self.state.explosions):
            explosion.timer -= 1
            if explosion.timer <= 0:
                self.state.explosions.remove(explosion)
        if self.check_victory():
            return
        self.state.block_regen_timer -= 1
        if self.state.block_regen_timer <= 0:
            core.try_regen_block(self.state)
            self.state.block_regen_timer = random.randint(BLOCK_REGEN_MIN_TIME, BLOCK_REGEN_MAX_TIME)

    def get_state(self) -> Dict[str, Any]:
        """Exports current state for sending to clients"""
        base = {
            "game_state": self.state.game_state,
            "players": {pid: vars(p) for pid, p in self.state.players.items()},
            "spectators": self.state.spectators,
            "chat_messages": self.state.chat_messages,
            "current_host_id": self.get_current_host()
        }
        if self.state.game_state == GAME_STATE_LOBBY:
            base["can_start"] = core.connected_players_count(self.state) >= 2
            base["can_spectator_join"] = core.can_spectator_join(self.state)
        elif self.state.game_state == GAME_STATE_PLAYING:
            base.update({
                "map": self.state.game_map,
                "bombs": [vars(b) for b in self.state.bombs],
                "explosions": [vars(e) for e in self.state.explosions]
            })
        elif self.state.game_state == GAME_STATE_VICTORY:
            base.update({
                "winner_id": self.state.winner_id,
                "victory_timer": self.state.victory_timer
            })
        return base

    def register_client_player(self, client_id: str, player_id: int) -> None:
        """Registers client-player mapping"""
        self.state.client_player_mapping[client_id] = player_id
        print(f"[REGISTER] Client {client_id} registered as Player {player_id}")

    def cleanup_client_mappings(self) -> None:
        """Cleans up obsolete mappings"""
        stale = [cid for cid, pid in self.state.client_player_mapping.items() if pid not in self.state.players]
        for cid in stale:
            del self.state.client_player_mapping[cid]
            print(f"[CLEANUP] Removed obsolete client mapping: {cid}")
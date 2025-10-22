from typing import Any, Dict
import random
from .models import (
    State,
    GAME_STATE_LOBBY, GAME_STATE_PLAYING, GAME_STATE_VICTORY,
    BLOCK_REGEN_MIN_TIME, BLOCK_REGEN_MAX_TIME
)
from .core import (
    add_player as core_add_player,
    get_current_host as core_get_current_host,
    start_game as core_start_game,
    return_to_lobby as core_return_to_lobby,
    connected_players_count, can_spectator_join,
    add_chat,
    place_bomb as core_place_bomb,
    move_player as core_move_player,
    explode_bomb as core_explode_bomb,
    check_victory as core_check_victory,
    try_regen_block
)

class S:
    """Game state constants"""
    GAME_STATE_LOBBY = GAME_STATE_LOBBY
    GAME_STATE_PLAYING = GAME_STATE_PLAYING
    GAME_STATE_VICTORY = GAME_STATE_VICTORY

class GameServer:
    """Main game server class"""
    def __init__(self):
        self.s = State()

    def add_player(self, player_id: int, name: str = "") -> None:
        """Adds a new player to the game"""
        core_add_player(self.s, player_id, name or f"Player {player_id}")
        if connected_players_count(self.s) == 1:
            self.s.current_host_id = player_id
            self.add_chat_message(-1, f"{name or f'Player {player_id}'} is the host", is_system=True)
        self.add_chat_message(-1, f"{name or f'Player {player_id}'} joined the lobby", is_system=True)

    def get_current_host(self) -> int:
        """Returns the current host ID"""
        return core_get_current_host(self.s)

    def start_game(self) -> bool:
        """Starts the game"""
        ok = core_start_game(self.s)
        if ok:
            self.add_chat_message(-1, "Game started! Good luck!", is_system=True)
        return ok

    def return_to_lobby(self) -> None:
        """Returns to lobby"""
        core_return_to_lobby(self.s)
        self.add_chat_message(-1, "Returned to lobby. Ready for a new game!", is_system=True)

    def add_spectator(self, name: str = "") -> int:
        """Adds a new spectator"""
        sid = self.s.next_spectator_id
        self.s.next_spectator_id += 1
        self.s.spectators[sid] = {
            "connected": True,
            "join_time": self.s.now(),
            "name": name or f"Spectator {sid}"
        }
        print(f"[SPECTATOR] Spectator {sid} ({name or f'Spectator {sid}'}) joined")
        self.add_chat_message(-1, f"{name or f'Spectator {sid}'} joined as spectator", is_system=True)
        return sid

    def remove_spectator(self, sid: int) -> None:
        """Removes a spectator"""
        if sid in self.s.spectators:
            name = self.s.spectators[sid].get("name", f"Spectator {sid}")
            del self.s.spectators[sid]
            print(f"[SPECTATOR] Spectator {sid} ({name}) left")
            self.add_chat_message(-1, f"{name} left", is_system=True)

    def convert_spectator_to_player(self, spectator_id: int, spectator_name: str = "") -> int:
        """Converts a spectator to a player"""
        if spectator_id not in self.s.spectators:
            return -1
        new_pid = None
        for i in range(4):
            if i not in self.s.players:
                new_pid = i
                break
        if new_pid is None:
            return -1
        name = self.s.spectators[spectator_id].get("name", spectator_name or f"Player {new_pid}")
        del self.s.spectators[spectator_id]
        self.add_player(new_pid, name)
        self.add_chat_message(-1, f"{name} joined as Player {new_pid}", is_system=True)
        return new_pid

    def handle_player_disconnect(self, player_id: int) -> None:
        """Handles player disconnection"""
        p = self.s.players.get(player_id)
        if not p:
            return
        player_name = p.name or f"Player {player_id}"
        print(f"[DISCONNECT] {player_name} disconnected")
        if self.s.game_state == GAME_STATE_LOBBY:
            if player_id in self.s.players:
                del self.s.players[player_id]
            stale = [cid for cid, pid in list(self.s.client_player_mapping.items()) if pid == player_id]
            for cid in stale:
                del self.s.client_player_mapping[cid]
            self.add_chat_message(-1, f"{player_name} left the lobby", is_system=True)
            if player_id == self.s.current_host_id:
                self.get_current_host()
        elif self.s.game_state == GAME_STATE_PLAYING:
            p.disconnected = True
            p.alive = False
            self.add_chat_message(-1, f"{player_name} disconnected", is_system=True)
            self.check_victory()

    def register_client_player(self, client_id: str, player_id: int) -> None:
        """Registers a client-player mapping"""
        self.s.client_player_mapping[client_id] = player_id
        print(f"[REGISTER] Client {client_id} registered as Player {player_id}")

    def cleanup_client_mappings(self) -> None:
        """Cleans up obsolete client mappings"""
        stale = [cid for cid, pid in self.s.client_player_mapping.items() if pid not in self.s.players]
        for cid in stale:
            del self.s.client_player_mapping[cid]
            print(f"[CLEANUP] Removed obsolete client mapping: {cid}")

    def add_chat_message(self, sender_id: int, message: str, is_system: bool = False):
        """Adds a chat message"""
        add_chat(self.s, sender_id, message, is_system=is_system)

    def move_player(self, player_id: int, direction: str) -> None:
        """Moves a player"""
        core_move_player(self.s, player_id, direction)

    def place_bomb(self, player_id: int) -> None:
        """Places a bomb"""
        core_place_bomb(self.s, player_id)

    def tick(self) -> None:
        """Game tick - updates game state"""
        if self.s.game_state == GAME_STATE_VICTORY:
            self.s.victory_timer -= 1
            if self.s.victory_timer <= 0:
                self.return_to_lobby()
            return
        if self.s.game_state != GAME_STATE_PLAYING:
            return
        for b in list(self.s.bombs):
            b.timer -= 1
            if b.timer <= 0:
                core_explode_bomb(self.s, b)
                self.s.bombs.remove(b)
        for e in list(self.s.explosions):
            e.timer -= 1
            if e.timer <= 0:
                self.s.explosions.remove(e)
        if core_check_victory(self.s):
            if self.s.winner_id == -1:
                self.add_chat_message(-1, "Draw - no winners!", is_system=True)
            else:
                winner_name = self.s.players[self.s.winner_id].name if self.s.winner_id in self.s.players else f"Player {self.s.winner_id}"
                self.add_chat_message(-1, f"{winner_name} wins the game!", is_system=True)
            return
        self.s.block_regen_timer -= 1
        if self.s.block_regen_timer <= 0:
            try_regen_block(self.s)
            self.s.block_regen_timer = random.randint(BLOCK_REGEN_MIN_TIME, BLOCK_REGEN_MAX_TIME)

    def check_victory(self) -> bool:
        """Checks for victory condition"""
        return core_check_victory(self.s)

    def get_state(self) -> Dict[str, Any]:
        """Returns current game state"""
        base = {
            "game_state": self.s.game_state,
            "players": {pid: vars(p) for pid, p in self.s.players.items()},
            "spectators": self.s.spectators,
            "chat_messages": self.s.chat_messages,
            "current_host_id": self.get_current_host()
        }
        if self.s.game_state == GAME_STATE_LOBBY:
            base["can_start"] = connected_players_count(self.s) >= 2
            base["can_spectator_join"] = can_spectator_join(self.s)
        elif self.s.game_state == GAME_STATE_PLAYING:
            base.update({
                "map": self.s.game_map,
                "bombs": [vars(b) for b in self.s.bombs],
                "explosions": [vars(e) for e in self.s.explosions]
            })
        elif self.s.game_state == GAME_STATE_VICTORY:
            base.update({
                "winner_id": self.s.winner_id,
                "victory_timer": self.s.victory_timer
            })
        return base
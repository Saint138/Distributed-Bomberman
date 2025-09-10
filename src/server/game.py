from typing import Any, Dict, Tuple, Optional
import time, random

from .models import (
    State, Player, Bomb, Explosion,
    GAME_STATE_LOBBY, GAME_STATE_PLAYING, GAME_STATE_VICTORY,
    DISCONNECT_TIMEOUT, BLOCK_REGEN_MIN_TIME, BLOCK_REGEN_MAX_TIME
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
    GAME_STATE_LOBBY   = GAME_STATE_LOBBY
    GAME_STATE_PLAYING = GAME_STATE_PLAYING
    GAME_STATE_VICTORY = GAME_STATE_VICTORY

class GameServer:
    def __init__(self):
        self.s = State()

    # ---------- Lobby / Host ----------
    def add_player(self, player_id: int, name: str = "") -> None:
        core_add_player(self.s, player_id, name or f"Player {player_id}")
        if connected_players_count(self.s) == 1:
            self.s.current_host_id = player_id
            self.add_chat_message(-1, f"{name or f'Player {player_id}'} is the host", is_system=True)
        self.add_chat_message(-1, f"{name or f'Player {player_id}'} joined the lobby", is_system=True)

    def get_current_host(self) -> int:
        return core_get_current_host(self.s)

    def start_game(self) -> bool:
        ok = core_start_game(self.s)
        if ok:
            self.add_chat_message(-1, "Game started! Good luck!", is_system=True)
        return ok

    def return_to_lobby(self) -> None:
        core_return_to_lobby(self.s)
        self.add_chat_message(-1, "Returned to lobby. Ready for a new game!", is_system=True)

    # ---------- Spettatori ----------
    def add_spectator(self, name: str = "") -> int:
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
        if sid in self.s.spectators:
            name = self.s.spectators[sid].get("name", f"Spectator {sid}")
            del self.s.spectators[sid]
            print(f"[SPECTATOR] Spectator {sid} ({name}) left")
            self.add_chat_message(-1, f"{name} left", is_system=True)

    def convert_spectator_to_player(self, spectator_id: int, spectator_name: str = "") -> int:
        if spectator_id not in self.s.spectators:
            return -1

        # trova slot libero o timeout scaduto
        new_pid = None
        for i in range(4):
            if i not in self.s.players:
                new_pid = i; break
            elif self.s.players[i].disconnected and self.s.players[i].disconnect_time_left <= 0:
                # ripulisci mapping obsoleti e libera slot
                stale = [cid for cid, pid in list(self.s.client_player_mapping.items()) if pid == i]
                for cid in stale:
                    del self.s.client_player_mapping[cid]
                del self.s.players[i]
                new_pid = i; break

        if new_pid is None:
            return -1

        # Rimuovi spettatore e aggiungi come player
        name = self.s.spectators[spectator_id].get("name", spectator_name or f"Player {new_pid}")
        del self.s.spectators[spectator_id]
        self.add_player(new_pid, name)

        self.add_chat_message(-1, f"{name} joined as Player {new_pid}", is_system=True)
        return new_pid

    # ---------- Reconnect ----------
    def register_client_player(self, client_id: str, player_id: int) -> None:
        self.s.client_player_mapping[client_id] = player_id
        print(f"[REGISTER] Client {client_id} registered as Player {player_id}")

    def handle_client_handshake(self, client_id: str):
        print(f"[HANDSHAKE] Checking client {client_id}")
        if client_id in self.s.client_player_mapping:
            pid = self.s.client_player_mapping[client_id]
            print(f"[HANDSHAKE] Client {client_id} was mapped to player {pid}")
            if pid not in self.s.players:
                print(f"[HANDSHAKE] Player {pid} no longer exists, removing mapping")
                del self.s.client_player_mapping[client_id]
                return None, None
            p = self.s.players[pid]
            if p.disconnected and p.disconnect_time_left > 0 and not p.already_reconnected and p.original_client_id == client_id:
                print(f"[HANDSHAKE] Valid reconnection for client {client_id} as player {pid}")
                return pid, False
            print(f"[HANDSHAKE] Invalid reconnection for client {client_id} → remove stale mapping")
            del self.s.client_player_mapping[client_id]
        print(f"[HANDSHAKE] Client {client_id} is a new connection")
        return None, None

    def cleanup_client_mappings(self) -> None:
        stale = [cid for cid, pid in self.s.client_player_mapping.items() if pid not in self.s.players]
        for cid in stale:
            del self.s.client_player_mapping[cid]
            print(f"[CLEANUP] Removed obsolete client mapping: {cid}")

    def handle_player_disconnect(self, player_id: int, temporarily_away: bool = False) -> None:
        p = self.s.players.get(player_id)
        if not p: return

        p.was_alive_before_disconnect = p.alive
        p.alive = False
        p.disconnected = True
        p.disconnect_time = time.time()
        p.disconnect_time_left = DISCONNECT_TIMEOUT
        p.already_reconnected = False
        p.temporarily_away = temporarily_away

        player_name = p.name or f"Player {player_id}"
        print(f"[DISCONNECT] {player_name} disconnected (client: {p.original_client_id})")

        if temporarily_away:
            self.add_chat_message(-1, f"{player_name} left temporarily", is_system=True)
        else:
            self.add_chat_message(-1, f"{player_name} disconnected", is_system=True)

        if self.s.game_state == GAME_STATE_LOBBY and player_id == self.get_current_host():
            self.get_current_host()
        if self.s.game_state == GAME_STATE_PLAYING:
            self.check_victory()

    def reconnect_player(self, player_id: int, client_id: str) -> bool:
        p = self.s.players.get(player_id)
        if not p: return False
        if (not p.disconnected) or p.disconnect_time_left <= 0 or p.already_reconnected: return False
        if p.original_client_id != client_id: return False

        p.disconnected = False
        p.disconnect_time = None
        p.disconnect_time_left = 0
        p.already_reconnected = True
        p.temporarily_away = False

        if self.s.game_state == GAME_STATE_PLAYING and p.was_alive_before_disconnect:
            p.alive = True

        player_name = p.name or f"Player {player_id}"
        self.add_chat_message(-1, f"{player_name} reconnected!", is_system=True)
        return True

    # ---------- Chat ----------
    def add_chat_message(self, sender_id: int, message: str, is_system: bool=False):
        add_chat(self.s, sender_id, message, is_system=is_system)

    # ---------- Input ----------
    def move_player(self, player_id: int, direction: str) -> None:
        core_move_player(self.s, player_id, direction)

    def place_bomb(self, player_id: int) -> None:
        core_place_bomb(self.s, player_id)

    # ---------- Tick / Orchestrazione ----------
    def tick(self) -> None:
        if self.s.game_state == GAME_STATE_VICTORY:
            self.s.victory_timer -= 1
            if self.s.victory_timer <= 0:
                self.return_to_lobby()
            return

        # aggiorna timeout reconnect
        now = time.time()
        to_remove = []
        for pid, p in self.s.players.items():
            if p.disconnected and p.disconnect_time:
                left = DISCONNECT_TIMEOUT - (now - p.disconnect_time)
                if left <= 0:
                    to_remove.append(pid)
                else:
                    p.disconnect_time_left = int(left)

        for pid in to_remove:
            player_name = self.s.players[pid].name if pid in self.s.players else f"Player {pid}"
            stale = [cid for cid, mapped in list(self.s.client_player_mapping.items()) if mapped == pid]
            for cid in stale:
                del self.s.client_player_mapping[cid]
            del self.s.players[pid]
            print(f"[TIMEOUT] {player_name} removed from game")
            self.add_chat_message(-1, f"{player_name} left the lobby", is_system=True)

        if self.s.game_state != GAME_STATE_PLAYING:
            return

        # bombe
        for b in list(self.s.bombs):
            b.timer -= 1
            if b.timer <= 0:
                core_explode_bomb(self.s, b)
                self.s.bombs.remove(b)

        # esplosioni
        for e in list(self.s.explosions):
            e.timer -= 1
            if e.timer <= 0:
                self.s.explosions.remove(e)

        # vittoria?
        if core_check_victory(self.s):
            if self.s.winner_id == -1:
                self.add_chat_message(-1, "Draw - no winners!", is_system=True)
            else:
                winner_name = self.s.players[self.s.winner_id].name if self.s.winner_id in self.s.players else f"Player {self.s.winner_id}"
                self.add_chat_message(-1, f"{winner_name} wins the game!", is_system=True)
            return

        # rigenerazione blocchi
        self.s.block_regen_timer -= 1
        if self.s.block_regen_timer <= 0:
            try_regen_block(self.s)
            self.s.block_regen_timer = random.randint(BLOCK_REGEN_MIN_TIME, BLOCK_REGEN_MAX_TIME)

    # ---------- Victory check wrapper ----------
    def check_victory(self) -> bool:
        return core_check_victory(self.s)

    # ---------- Stato ----------
    def get_state(self) -> Dict[str, Any]:
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
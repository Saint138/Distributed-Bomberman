from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Tuple, Optional
import time as _time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.constants import MAX_MESSAGE_LENGTH, MAX_CHAT_MESSAGES

MAP_WIDTH = 15
MAP_HEIGHT = 13
TILE_EMPTY, TILE_WALL, TILE_BLOCK, TILE_BOMB, TILE_FIRE = 0, 1, 2, 3, 4

GAME_STATE_LOBBY = "lobby"
GAME_STATE_PLAYING = "playing"
GAME_STATE_VICTORY = "victory"

BOMB_TIMER_TICKS = 20
EXPLOSION_TTL_TICKS = 5
EXPLOSION_RANGE = 2
BLOCK_REGEN_MIN_TIME = 30
BLOCK_REGEN_MAX_TIME = 80
MAX_BLOCKS_ON_MAP = 30
DISCONNECT_TIMEOUT = 20

@dataclass
class Player:
    """Represents a player in the game"""
    x: int
    y: int
    name: str = ""
    alive: bool = True
    lives: int = 3
    disconnected: bool = False
    disconnect_time: Optional[float] = None
    disconnect_time_left: int = 0
    ready: bool = False
    was_player: bool = True
    original_client_id: Optional[str] = None
    already_reconnected: bool = False
    was_alive_before_disconnect: bool = True
    temporarily_away: bool = False

@dataclass
class Bomb:
    """Represents a bomb on the map"""
    x: int
    y: int
    timer: int
    owner: int

@dataclass
class Explosion:
    """Represents an explosion effect"""
    positions: List[Tuple[int, int]]
    timer: int

@dataclass
class State:
    """Represents the complete game state"""
    game_state: str = GAME_STATE_LOBBY
    winner_id: Optional[int] = None
    victory_timer: int = 0
    game_map: List[List[int]] = field(default_factory=list)
    bombs: List[Bomb] = field(default_factory=list)
    explosions: List[Explosion] = field(default_factory=list)
    players: Dict[int, Player] = field(default_factory=dict)
    spectators: Dict[int, dict] = field(default_factory=dict)
    current_host_id: int = 0
    next_spectator_id: int = 100
    chat_messages: List[dict] = field(default_factory=list)
    client_player_mapping: Dict[str, int] = field(default_factory=dict)
    block_regen_timer: int = BLOCK_REGEN_MIN_TIME

    @staticmethod
    def now() -> float:
        """Returns current timestamp"""
        return _time.time()
    

STATE_VERSION = 1


def state_to_dict(state: "State") -> Dict[str, Any]:
    """Convert a State into a plain dict ready to be JSON-encoded."""
    return {
        "version": STATE_VERSION,
        "game_state": state.game_state,
        "winner_id": state.winner_id,
        "victory_timer": state.victory_timer,
        "game_map": state.game_map,
        "bombs": [asdict(b) for b in state.bombs],
        "explosions": [
            {"positions": [list(p) for p in e.positions], "timer": e.timer}
            for e in state.explosions
        ],
        "players": {str(pid): asdict(p) for pid, p in state.players.items()},
        "spectators": {str(sid): dict(s) for sid, s in state.spectators.items()},
        "current_host_id": state.current_host_id,
        "next_spectator_id": state.next_spectator_id,
        "chat_messages": list(state.chat_messages),
        "client_player_mapping": dict(state.client_player_mapping),
        "block_regen_timer": state.block_regen_timer,
    }


def state_from_dict(d: Dict[str, Any]) -> "State":
    if d.get("version") != STATE_VERSION:
        raise ValueError(
            f"Unsupported snapshot version: got {d.get('version')!r}, "
            f"expected {STATE_VERSION}"
        )
    return State(
        game_state=d["game_state"],
        winner_id=d.get("winner_id"),
        victory_timer=d.get("victory_timer", 0),
        game_map=[list(row) for row in d.get("game_map", [])],
        bombs=[Bomb(**b) for b in d.get("bombs", [])],
        explosions=[
            Explosion(
                positions=[tuple(p) for p in e["positions"]],
                timer=e["timer"],
            )
            for e in d.get("explosions", [])
        ],
        # Convert string keys back to int (JSON forced them to strings).
        players={int(pid): Player(**p) for pid, p in d.get("players", {}).items()},
        spectators={int(sid): dict(s) for sid, s in d.get("spectators", {}).items()},
        current_host_id=d.get("current_host_id", 0),
        next_spectator_id=d.get("next_spectator_id", 100),
        chat_messages=list(d.get("chat_messages", [])),
        client_player_mapping=dict(d.get("client_player_mapping", {})),
        block_regen_timer=d.get("block_regen_timer", BLOCK_REGEN_MIN_TIME),
    )
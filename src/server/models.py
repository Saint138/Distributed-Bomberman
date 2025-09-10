from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional
import time as _time

# --- Costanti mappa ---
MAP_WIDTH  = 15
MAP_HEIGHT = 13
TILE_EMPTY, TILE_WALL, TILE_BLOCK, TILE_BOMB, TILE_FIRE = 0, 1, 2, 3, 4

# --- Stati di gioco ---
GAME_STATE_LOBBY   = "lobby"
GAME_STATE_PLAYING = "playing"
GAME_STATE_VICTORY = "victory"

# --- Gameplay / Sessione ---
BOMB_TIMER_TICKS     = 20
EXPLOSION_TTL_TICKS  = 5
EXPLOSION_RANGE      = 2
BLOCK_REGEN_MIN_TIME = 30
BLOCK_REGEN_MAX_TIME = 80
MAX_BLOCKS_ON_MAP    = 30
DISCONNECT_TIMEOUT   = 20
MAX_CHAT_MESSAGES    = 10
MAX_MESSAGE_LENGTH   = 50

@dataclass
class Player:
    x: int
    y: int
    name: str = ""  # Aggiunto campo nome
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
    temporarily_away: bool = False  # Aggiunto per distinguere uscite temporanee

@dataclass
class Bomb:
    x: int
    y: int
    timer: int
    owner: int

@dataclass
class Explosion:
    positions: List[Tuple[int, int]]
    timer: int

@dataclass
class State:
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

    def now(self) -> float:
        return _time.time()
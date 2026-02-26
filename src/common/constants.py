# src/common/constants.py
"""
Costanti condivise tra client e server.
"""

# ── Mappa ───────────────────────────────────────────────────────────────────
TILE_SIZE  = 32
MAP_WIDTH  = 15
MAP_HEIGHT = 13

# Tipi di tile
TILE_EMPTY = 0
TILE_WALL  = 1
TILE_BLOCK = 2
TILE_BOMB  = 3
TILE_FIRE  = 4

# Stati di gioco
GAME_STATE_LOBBY   = "lobby"
GAME_STATE_PLAYING = "playing"
GAME_STATE_VICTORY = "victory"

# ── Colori ───────────────────────────────────────────────────────────────────
TILE_COLORS = {
    TILE_EMPTY: (30, 30, 30),
    TILE_WALL:  (100, 100, 100),
    TILE_BLOCK: (150, 75, 0),
    TILE_BOMB:  (255, 0, 0),
    TILE_FIRE:  (255, 165, 0),
}

PLAYER_COLORS = [
    (0, 255, 0),    # Player 0 - Verde
    (0, 0, 255),    # Player 1 - Blu
    (255, 255, 0),  # Player 2 - Giallo
    (255, 0, 255),  # Player 3 - Magenta
]

UI_COLORS = {
    'bg_dark':        (15, 15, 20),
    'bg_medium':      (25, 25, 35),
    'bg_light':       (35, 35, 45),
    'border':         (60, 60, 80),
    'border_light':   (80, 80, 100),
    'text_primary':   (255, 255, 255),
    'text_secondary': (200, 200, 200),
    'text_disabled':  (120, 120, 120),
    'success':        (50, 255, 100),
    'danger':         (255, 80, 80),
    'warning':        (255, 200, 50),
    'info':           (100, 200, 255),
}

# ── Gameplay ─────────────────────────────────────────────────────────────────
BOMB_TIMER_TICKS    = 20
EXPLOSION_TTL_TICKS = 5
EXPLOSION_RANGE     = 2
PLAYER_LIVES        = 3

# ── Network ──────────────────────────────────────────────────────────────────
MAX_PLAYERS  = 4
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555   # PROXY_FRONTEND_PORT  ← client usa questa

#──────────────────────────────────────
#
#   5555  PROXY_FRONTEND_PORT    ← client connect here
#   5556  PRIMARY_GAME_PORT      ← primary (and promoted backup) serve here
#   5557  BACKUP_STATE_PORT      ← backup receives state snapshots here
#   5558  BACKUP_GAME_PORT       ← backup game port (before promotion)
#   5565  PRIMARY_HEARTBEAT_PORT ← primary responds HEARTBEAT→ALIVE here
#
def _make_ports(base: int = 5555) -> dict:
    return {
        "proxy_frontend":    base,
        "primary_game":      base + 1,
        "backup_state":      base + 2,
        "backup_game":       base + 3,
        "primary_heartbeat": base + 10,
    }

_PORTS = _make_ports(5555)

PROXY_FRONTEND_PORT    = _PORTS["proxy_frontend"]     # 5555
PRIMARY_GAME_PORT      = _PORTS["primary_game"]        # 5556
BACKUP_STATE_PORT      = _PORTS["backup_state"]        # 5557
BACKUP_GAME_PORT       = _PORTS["backup_game"]         # 5558
PRIMARY_HEARTBEAT_PORT = _PORTS["primary_heartbeat"]   # 5565

# ── Chat ─────────────────────────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 150
MAX_CHAT_MESSAGES  = 100
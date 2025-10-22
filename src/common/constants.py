# Costanti condivise tra client e server

# Dimensioni tile e mappa
TILE_SIZE = 32
MAP_WIDTH = 15
MAP_HEIGHT = 13

# Tipi di tile
TILE_EMPTY = 0
TILE_WALL = 1
TILE_BLOCK = 2
TILE_BOMB = 3
TILE_FIRE = 4

# Stati di gioco
GAME_STATE_LOBBY = "lobby"
GAME_STATE_PLAYING = "playing"
GAME_STATE_VICTORY = "victory"

# Colori tile
TILE_COLORS = {
    TILE_EMPTY: (30, 30, 30),
    TILE_WALL: (100, 100, 100),
    TILE_BLOCK: (150, 75, 0),
    TILE_BOMB: (255, 0, 0),
    TILE_FIRE: (255, 165, 0),
}

# Colori giocatori
PLAYER_COLORS = [
    (0, 255, 0),    # Player 0 - Verde
    (0, 0, 255),    # Player 1 - Blu
    (255, 255, 0),  # Player 2 - Giallo
    (255, 0, 255)   # Player 3 - Magenta
]

# Palette colori UI
UI_COLORS = {
    'bg_dark': (15, 15, 20),
    'bg_medium': (25, 25, 35),
    'bg_light': (35, 35, 45),
    'border': (60, 60, 80),
    'border_light': (80, 80, 100),
    'text_primary': (255, 255, 255),
    'text_secondary': (200, 200, 200),
    'text_disabled': (120, 120, 120),
    'success': (50, 255, 100),
    'danger': (255, 80, 80),
    'warning': (255, 200, 50),
    'info': (100, 200, 255)
}

# Gameplay
BOMB_TIMER_TICKS = 20
EXPLOSION_TTL_TICKS = 5
EXPLOSION_RANGE = 2
PLAYER_LIVES = 3

# Network
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555
MAX_PLAYERS = 4

# Chat
MAX_MESSAGE_LENGTH = 150
MAX_CHAT_MESSAGES = 100
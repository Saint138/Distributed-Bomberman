import random
from typing import Tuple, Optional, Set
from .models import (
    State, Player, Bomb, Explosion,
    MAP_WIDTH, MAP_HEIGHT, TILE_EMPTY, TILE_WALL, TILE_BLOCK,
    GAME_STATE_PLAYING, GAME_STATE_VICTORY, GAME_STATE_LOBBY,
    BOMB_TIMER_TICKS, EXPLOSION_RANGE, EXPLOSION_TTL_TICKS,
    BLOCK_REGEN_MIN_TIME, MAX_BLOCKS_ON_MAP,
    MAX_MESSAGE_LENGTH, MAX_CHAT_MESSAGES
)

# Costanti per direzioni
DIRECTIONS = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0)
}

# Direzioni cardinali per esplosioni
CARDINAL_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def get_safe_zones() -> Set[Tuple[int, int]]:
    """Ritorna l'insieme delle zone sicure (spawn areas)"""
    return {
        (1, 1), (1, 2), (2, 1),
        (1, MAP_HEIGHT-2), (1, MAP_HEIGHT-3), (2, MAP_HEIGHT-2),
        (MAP_WIDTH-2, 1), (MAP_WIDTH-3, 1), (MAP_WIDTH-2, 2),
        (MAP_WIDTH-2, MAP_HEIGHT-2), (MAP_WIDTH-2, MAP_HEIGHT-3), (MAP_WIDTH-3, MAP_HEIGHT-2)
    }


def connected_players_count(s: State) -> int:
    """Returns the number of connected players"""
    return sum(1 for p in s.players.values() if not p.disconnected)


def can_spectator_join(s: State) -> bool:
    """Checks if a spectator can join as a player"""
    free = 0
    for i in range(4):
        if i not in s.players:
            free += 1
        elif s.players[i].disconnected and s.players[i].disconnect_time_left <= 0:
            free += 1
    return free > 0


def add_chat(s: State, sender_id: int, message: str, is_system: bool = False):
    """Adds a chat message to the game state"""
    msg = (message or "")[:MAX_MESSAGE_LENGTH]
    is_spectator = (sender_id >= 100) if not is_system else False
    s.chat_messages.append({
        "player_id": sender_id,
        "message": msg,
        "timestamp": s.now(),
        "is_system": is_system,
        "is_spectator": is_spectator
    })
    if len(s.chat_messages) > MAX_CHAT_MESSAGES:
        s.chat_messages[:] = s.chat_messages[-MAX_CHAT_MESSAGES:]
    if not is_system:
        who = "Spectator" if is_spectator else "Player"
        print(f"[CHAT] {who} {sender_id}: {msg}")


def spawn_for(pid: int) -> Tuple[int, int]:
    """Returns spawn coordinates for a player ID"""
    return [(1, 1), (1, MAP_HEIGHT-2), (MAP_WIDTH-2, 1), (MAP_WIDTH-2, MAP_HEIGHT-2)][pid % 4]


def add_player(s: State, pid: int, name: str = ""):
    """Adds a new player to the game"""
    x, y = spawn_for(pid)
    s.players[pid] = Player(x=x, y=y, name=name or f"Player {pid}")
    print(f"[LOBBY] Player {pid} ({name or f'Player {pid}'}) joined the lobby")


def get_current_host(s: State) -> int:
    """Gets or reassigns the current host"""
    if s.current_host_id in s.players and not s.players[s.current_host_id].disconnected:
        return s.current_host_id
    connected = [pid for pid, p in s.players.items() if not p.disconnected]
    if connected:
        s.current_host_id = min(connected)
        print(f"[HOST] Player {s.current_host_id} is now the host")
        add_chat(s, -1, f"Player {s.current_host_id} is now the host", is_system=True)
    return s.current_host_id


def reset_positions(s: State):
    """Resets all player positions and states"""
    for pid, p in s.players.items():
        if not p.disconnected:
            p.x, p.y = spawn_for(pid)
            p.alive, p.lives = True, 3


def start_game(s: State) -> bool:
    """Starts a new game"""
    if s.game_state != GAME_STATE_LOBBY:
        return False
    if connected_players_count(s) < 2:
        print("[START] Cannot start: need at least 2 players")
        return False
    s.game_state = GAME_STATE_PLAYING
    s.game_map = generate_map()
    reset_positions(s)
    print("[START] Starting game!")
    return True


def return_to_lobby(s: State):
    """Returns to lobby and cleans up game state"""
    print("[GAME] Returning to lobby...")
    s.game_state = GAME_STATE_LOBBY
    s.game_map = []
    s.bombs.clear()
    s.explosions.clear()
    s.winner_id = None
    s.victory_timer = 0
    s.block_regen_timer = BLOCK_REGEN_MIN_TIME
    disconnected_players = []
    for pid, p in list(s.players.items()):
        if p.disconnected:
            disconnected_players.append(pid)
            print(f"[CLEANUP] Removing disconnected player {pid} ({p.name}) from lobby")
        else:
            p.ready = False
            p.alive = True
            p.lives = 3
    for pid in disconnected_players:
        if pid in s.players:
            del s.players[pid]
    stale_mappings = [cid for cid, pid in list(s.client_player_mapping.items()) if pid in disconnected_players]
    for cid in stale_mappings:
        del s.client_player_mapping[cid]


def generate_map():
    """Generates a new game map"""
    safe_zones = get_safe_zones()
    m = [[TILE_EMPTY for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if x in (0, MAP_WIDTH-1) or y in (0, MAP_HEIGHT-1):
                m[y][x] = TILE_WALL
            elif x % 2 == 0 and y % 2 == 0:
                m[y][x] = TILE_WALL
            elif (x, y) not in safe_zones and random.random() < 0.2:
                m[y][x] = TILE_BLOCK
    return m


def is_walkable(s: State, x: int, y: int) -> bool:
    """Checks if a tile is walkable"""
    return bool(s.game_map) and 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and s.game_map[y][x] == TILE_EMPTY


def is_player_at(s: State, x: int, y: int, exclude_id: Optional[int] = None) -> bool:
    """Checks if a player is at given coordinates"""
    for pid, p in s.players.items():
        if exclude_id is not None and pid == exclude_id:
            continue
        if p.alive and not p.disconnected and p.x == x and p.y == y:
            return True
    return False


def move_player(s: State, pid: int, direction: str):
    """Moves a player in the specified direction"""
    if s.game_state != GAME_STATE_PLAYING:
        return
    if pid not in s.players or not s.players[pid].alive:
        return
    dx, dy = DIRECTIONS.get(direction, (0, 0))
    px, py = s.players[pid].x, s.players[pid].y
    nx, ny = px + dx, py + dy
    if is_walkable(s, nx, ny) and not is_player_at(s, nx, ny, exclude_id=pid):
        s.players[pid].x, s.players[pid].y = nx, ny


def place_bomb(s: State, pid: int):
    """Places a bomb at the player's position"""
    if s.game_state != GAME_STATE_PLAYING:
        return
    if pid not in s.players or not s.players[pid].alive:
        return
    x, y = s.players[pid].x, s.players[pid].y
    if any(b.x == x and b.y == y for b in s.bombs):
        return
    s.bombs.append(Bomb(x=x, y=y, timer=BOMB_TIMER_TICKS, owner=pid))


def explode_bomb(s: State, bomb: Bomb):
    """Explodes a bomb and creates explosion effect"""
    x, y = bomb.x, bomb.y
    affected = [(x, y)]
    for dx, dy in CARDINAL_DIRECTIONS:
        for r in range(1, EXPLOSION_RANGE + 1):
            nx, ny = x + dx*r, y + dy*r
            if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                break
            tile = s.game_map[ny][nx]
            if tile == TILE_WALL:
                break
            affected.append((nx, ny))
            if tile == TILE_BLOCK:
                s.game_map[ny][nx] = TILE_EMPTY
                break
    for pid, p in s.players.items():
        if p.alive and (p.x, p.y) in affected:
            p.lives -= 1
            if p.lives <= 0:
                p.alive = False
                print(f"[ELIMINATED] Player {pid} eliminated!")
    s.explosions.append(Explosion(positions=affected, timer=EXPLOSION_TTL_TICKS))


def check_victory(s: State) -> bool:
    """Checks if there's a winner"""
    if s.game_state != GAME_STATE_PLAYING:
        return False
    alive = [pid for pid, p in s.players.items() if p.alive and not p.disconnected and p.lives > 0]
    if len(alive) == 1:
        s.winner_id = alive[0]
        s.game_state = GAME_STATE_VICTORY
        s.victory_timer = 50
        print(f"[VICTORY] Player {s.winner_id} wins!")
        return True
    if len(alive) == 0:
        s.winner_id = -1
        s.game_state = GAME_STATE_VICTORY
        s.victory_timer = 50
        print("[VICTORY] Draw - no winners!")
        return True
    return False


def safe_to_place_block(s: State, x: int, y: int) -> bool:
    """Checks if it's safe to place a block at given position"""
    if not s.game_map or s.game_map[y][x] != TILE_EMPTY:
        return False
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = x+dx, y+dy
            if 0 <= cx < MAP_WIDTH and 0 <= cy < MAP_HEIGHT:
                for p in s.players.values():
                    if not p.disconnected and p.alive and p.x == cx and p.y == cy:
                        return False
    safe_zones = get_safe_zones()
    return (x, y) not in safe_zones


def try_regen_block(s: State):
    """Attempts to regenerate a block on the map"""
    current = sum(1 for row in s.game_map for t in row if t == TILE_BLOCK)
    if current >= MAX_BLOCKS_ON_MAP:
        return
    for _ in range(50):
        x = random.randint(1, MAP_WIDTH-2)
        y = random.randint(1, MAP_HEIGHT-2)
        if safe_to_place_block(s, x, y):
            s.game_map[y][x] = TILE_BLOCK
            print(f"[BLOCK REGEN] block at ({x},{y})")
            return
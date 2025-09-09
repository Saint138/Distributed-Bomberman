# server/game_logic.py
import random
import time

MAP_WIDTH = 15
MAP_HEIGHT = 13

TILE_EMPTY = 0
TILE_WALL  = 1
TILE_BLOCK = 2
TILE_BOMB  = 3
TILE_FIRE  = 4  

GAME_STATE_LOBBY = "lobby"
GAME_STATE_PLAYING = "playing"
GAME_STATE_VICTORY = "victory"

BOMB_TIMER_TICKS     = 20   
EXPLOSION_RANGE      = 2
EXPLOSION_TTL_TICKS  = 5
RECONNECT_TIMEOUT_S  = 20
MAX_BOMBS_PER_PLAYER = 1    

DISCONNECT_TIMEOUT = 20 

MAX_CHAT_MESSAGES = 10
MAX_MESSAGE_LENGTH = 50

class GameState:
    def __init__(self):
        self.map = self._generate_map()
        self.players = {}       
        self.bombs = []        
        self.explosions = []   
        self.client_player_mapping = {}
        self.spectators = {}
        self.chat_messages = []
        self.next_spectator_id = 100
        self.game_state = GAME_STATE_LOBBY
        self.winner_id = None
        self.victory_timer = 0

        

    # ---------------- Map/Spawn ----------------

    def _generate_map(self):
        spawn_safe_zones = {
            (1, 1), (1, 2), (2, 1),
            (1, MAP_HEIGHT - 2), (1, MAP_HEIGHT - 3), (2, MAP_HEIGHT - 2),
            (MAP_WIDTH - 2, 1), (MAP_WIDTH - 3, 1), (MAP_WIDTH - 2, 2),
            (MAP_WIDTH - 2, MAP_HEIGHT - 2), (MAP_WIDTH - 2, MAP_HEIGHT - 3), (MAP_WIDTH - 3, MAP_HEIGHT - 2)
        }

        m = [[TILE_EMPTY for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if x == 0 or y == 0 or x == MAP_WIDTH - 1 or y == MAP_HEIGHT - 1:
                    m[y][x] = TILE_WALL
                elif x % 2 == 0 and y % 2 == 0:
                    m[y][x] = TILE_WALL
                elif (x, y) not in spawn_safe_zones and random.random() < 0.2:
                    m[y][x] = TILE_BLOCK
        return m

    def add_player(self, player_id):
        spawn = [(1,1), (1, MAP_HEIGHT-2), (MAP_WIDTH-2,1), (MAP_WIDTH-2, MAP_HEIGHT-2)]
        x, y = spawn[player_id % len(spawn)]
        self.players[player_id] = {
            "x": x, "y": y, "alive": True, "lives": 3,
            "disconnected": False, "disconnect_time": None,
            "disconnect_time_left": 0
        }
    def start_game(self):
        if self.game_state != GAME_STATE_LOBBY: return False
        if sum(1 for p in self.players.values() if not p.get("disconnected", False)) < 2:
            return False
        self.game_state = GAME_STATE_PLAYING
        self.map = self._generate_map()
        # reset posizioni/ vite
        spawn = [(1,1),(1,MAP_HEIGHT-2),(MAP_WIDTH-2,1),(MAP_WIDTH-2,MAP_HEIGHT-2)]
        for pid, pd in self.players.items():
            if pid < len(spawn) and not pd.get("disconnected", False):
                pd["x"], pd["y"] = spawn[pid]
                pd["alive"], pd["lives"] = True, 3
        return True

    def return_to_lobby(self):
        self.game_state = GAME_STATE_LOBBY
        self.map, self.bombs, self.explosions = None, [], []
        self.winner_id, self.victory_timer = None, 0
        for pd in self.players.values():
            if not pd.get("disconnected", False):
                pd["alive"], pd["lives"] = True, 3

    # ---------------- Spectator/player Management ----------------
    def add_spectator(self):
        sid = self.next_spectator_id; self.next_spectator_id += 1
        self.spectators[sid] = {"connected": True, "join_time": time.time()}
        self.add_chat_message(-1, f"Spectator {sid} joined", is_system=True)
        return sid

    def remove_spectator(self, sid):
        if sid in self.spectators:
            del self.spectators[sid]
            self.add_chat_message(-1, f"Spectator {sid} left", is_system=True)

    def add_chat_message(self, sender_id, message, is_system=False):
        message = message[:MAX_MESSAGE_LENGTH]
        is_spectator = (sender_id >= 100) if not is_system else False
        self.chat_messages.append({
            "player_id": sender_id,
            "message": message,
            "timestamp": time.time(),
            "is_system": is_system,
            "is_spectator": is_spectator
        })
        if len(self.chat_messages) > MAX_CHAT_MESSAGES:
            self.chat_messages = self.chat_messages[-MAX_CHAT_MESSAGES:]

    def handle_client_handshake(self, client_id):
        if client_id in self.client_player_mapping:
            pid = self.client_player_mapping[client_id]
            if pid not in self.players:
                del self.client_player_mapping[client_id]
                return None, None
            pd = self.players[pid]
            if (pd.get("disconnected", False) and
                pd.get("disconnect_time_left", 0) > 0 and
                not pd.get("already_reconnected", False) and
                pd.get("original_client_id") == client_id):
                return pid, False
            # mapping obsoleta
            del self.client_player_mapping[client_id]
        return None, None

    def register_client_player(self, client_id, player_id):
        self.client_player_mapping[client_id] = player_id

    def handle_player_disconnect(self, player_id):
        if player_id not in self.players: return
        pd = self.players[player_id]
        pd["was_alive_before_disconnect"] = pd.get("alive", False)
        pd["alive"] = False
        pd["disconnected"] = True
        pd["disconnect_time"] = time.time()
        pd["disconnect_time_left"] = DISCONNECT_TIMEOUT
        pd["already_reconnected"] = False

    def reconnect_player(self, player_id, client_id):
        if player_id not in self.players: return False
        pd = self.players[player_id]
        if (not pd.get("disconnected", False) or
            pd.get("disconnect_time_left", 0) <= 0 or
            pd.get("already_reconnected", False)):
            return False
        if pd.get("original_client_id") != client_id:
            return False
        pd["disconnected"] = False
        pd["disconnect_time"] = None
        pd["disconnect_time_left"] = 0
        pd["already_reconnected"] = True
        if pd.get("was_alive_before_disconnect", True):
            pd["alive"] = True
        return True

    def cleanup_client_mappings(self):
        stale = [cid for cid, pid in self.client_player_mapping.items() if pid not in self.players]
        for cid in stale:
            del self.client_player_mapping[cid]


    # ---------------- Movement ----------------

    def _is_walkable(self, x, y):
        return 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and self.map[y][x] == TILE_EMPTY

    def _bomb_at(self, x, y):
        return any(b["x"] == x and b["y"] == y and b.get("timer", 0) > 0 for b in self.bombs)

    def move_player(self, player_id, direction):
        if player_id not in self.players or not self.players[player_id]["alive"]:
            return
        dx, dy = {"UP":(0,-1), "DOWN":(0,1), "LEFT":(-1,0), "RIGHT":(1,0)}.get(direction, (0,0))
        px, py = self.players[player_id]["x"], self.players[player_id]["y"]
        nx, ny = px + dx, py + dy
        if self._is_walkable(nx, ny) and not self._bomb_at(nx, ny):
            self.players[player_id]["x"], self.players[player_id]["y"] = nx, ny

    # ---------------- Bombs / Explosions ----------------

    def place_bomb(self, player_id):
        if player_id not in self.players:
            return
        p = self.players[player_id]
        if not p["alive"]:
            return

        active_bombs = sum(1 for b in self.bombs if b["owner"] == player_id and b.get("timer", 0) > 0)
        if active_bombs >= MAX_BOMBS_PER_PLAYER:
            return

        x, y = p["x"], p["y"]
        if self._bomb_at(x, y):
            return

        self.bombs.append({"x": x, "y": y, "timer": BOMB_TIMER_TICKS, "owner": player_id})

    def explode_bomb(self, bomb):
        x, y = bomb["x"], bomb["y"]
        affected_positions = [(x, y)]
        directions = [(-1,0),(1,0),(0,-1),(0,1)]

        for dx, dy in directions:
            for r in range(1, EXPLOSION_RANGE + 1):
                nx, ny = x + dx*r, y + dy*r
                if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                    break
                tile = self.map[ny][nx]
                if tile == TILE_WALL:
                    break
                affected_positions.append((nx, ny))
                if tile == TILE_BLOCK:
                    self.map[ny][nx] = TILE_EMPTY
                    break

        # danno ai player colpiti
        for pid, pdata in self.players.items():
            if pdata["alive"] and (pdata["x"], pdata["y"]) in affected_positions:
                pdata["lives"] -= 1
                if pdata["lives"] <= 0:
                    pdata["alive"] = False

        # traccia esplosione attiva per qualche tick (per il rendering)
        self.explosions.append({"positions": affected_positions, "timer": EXPLOSION_TTL_TICKS})

    # ---------------- Tick / Cleanup ----------------

    def tick(self):
        for b in list(self.bombs):
            b["timer"] -= 1
            if b["timer"] <= 0:
                self.explode_bomb(b)
                self.bombs.remove(b)

        for exp in list(self.explosions):
            exp["timer"] -= 1
            if exp["timer"] <= 0:
                self.explosions.remove(exp)

        now = time.time()
        to_remove = []
        for pid, pd in self.players.items():
            if pd.get("disconnected", False) and pd.get("disconnect_time"):
                left = DISCONNECT_TIMEOUT - (now - pd["disconnect_time"])
                if left <= 0:
                    to_remove.append(pid)
                else:
                    pd["disconnect_time_left"] = int(left)
        for pid in to_remove:
            del self.players[pid]


    # ---------------- Serialization ----------------

    def get_state(self):
        return {
            "map": self.map,
            "players": self.players,
            "bombs": self.bombs,
            "explosions": self.explosions,
            "spectators": self.spectators,  # opzionale se il client lo usa
            "chat_messages": self.chat_messages,
            "game_state": self.game_state,
            "winner_id": self.winner_id,
            "victory_timer": self.victory_timer,
        }

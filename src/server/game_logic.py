import random
import time

# server/game_logic.py
MAP_WIDTH = 15
MAP_HEIGHT = 13

TILE_EMPTY = 0
TILE_WALL  = 1
TILE_BLOCK = 2  # <-- nuovo: blocco distruttibile
TILE_BOMB  = 3
TILE_FIRE  = 4

class GameState:
    def __init__(self):
        self.map = self._generate_map()
        self.players = {}
        self.bombs = []        # <-- prepariamo già le liste
        self.explosions = []   # <-- per step successivi

    def _generate_map(self):
        spawn_safe_zones = {(1, 1), (1, 2), (2, 1),
                            (1, MAP_HEIGHT - 2), (1, MAP_HEIGHT - 3), (2, MAP_HEIGHT - 2),
                            (MAP_WIDTH - 2, 1), (MAP_WIDTH - 3, 1), (MAP_WIDTH - 2, 2),
                            (MAP_WIDTH - 2, MAP_HEIGHT - 2), (MAP_WIDTH - 2, MAP_HEIGHT - 3), (MAP_WIDTH - 3, MAP_HEIGHT - 2)}

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
        x,y = spawn[player_id % len(spawn)]
        self.players[player_id] = {
            "x": x, "y": y, "alive": True, "lives": 3,
            "disconnected": False, "disconnect_time": None   # <-- aggiunti
        }


    def move_player(self, player_id, direction):
        if player_id not in self.players or not self.players[player_id]["alive"]:
            return
        dx, dy = {"UP":(0,-1), "DOWN":(0,1), "LEFT":(-1,0), "RIGHT":(1,0)}.get(direction, (0,0))
        px, py = self.players[player_id]["x"], self.players[player_id]["y"]
        nx, ny = px + dx, py + dy
        if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT and self.map[ny][nx] == TILE_EMPTY:
            self.players[player_id]["x"], self.players[player_id]["y"] = nx, ny
    
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
        for pid in list(self.players):
            pdata = self.players[pid]
            if pdata.get("disconnected") and pdata.get("disconnect_time") and now - pdata["disconnect_time"] > 20:
                print(f"[TIMEOUT] Player {pid} removed from game")
                del self.players[pid]

    def get_state(self):
        return {
            "map": self.map,
            "players": self.players,
            "bombs": self.bombs,
            "explosions": self.explosions
        }
    
    def place_bomb(self, player_id):
        if player_id not in self.players:
            return
        p = self.players[player_id]
        if not p["alive"]:
            return
        x, y = p["x"], p["y"]
        # aggiungi una bomba con timer 20 tick
        self.bombs.append({"x": x, "y": y, "timer": 20, "owner": player_id})

    def explode_bomb(self, bomb):
        x, y = bomb["x"], bomb["y"]
        affected = [(x, y)]
        directions = [(-1,0),(1,0),(0,-1),(0,1)]
        explosion_range = 2

        for dx, dy in directions:
            for r in range(1, explosion_range + 1):
                nx, ny = x + dx*r, y + dy*r
                if not (0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT):
                    break
                tile = self.map[ny][nx]
                if tile == TILE_WALL:
                    break
                affected.append((nx, ny))
                if tile == TILE_BLOCK:
                    self.map[ny][nx] = TILE_EMPTY
                    break

        # danno ai player colpiti
        for pid, pdata in self.players.items():
            if pdata["alive"] and (pdata["x"], pdata["y"]) in affected:
                pdata["lives"] -= 1
                if pdata["lives"] <= 0:
                    pdata["alive"] = False

        # traccia esplosione attiva per 5 tick
        self.explosions.append({"positions": affected, "timer": 5})
# server/game_logic.py
MAP_WIDTH = 15
MAP_HEIGHT = 13

TILE_EMPTY = 0
TILE_WALL = 1

class GameState:
    def __init__(self):
        self.map = self._generate_map()
        self.players = {}  # pid -> {"x","y","alive","lives"}

    def _generate_map(self):
        # mura perimetrali, interno vuoto (versione minimale)
        m = [[TILE_EMPTY for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                if x == 0 or y == 0 or x == MAP_WIDTH-1 or y == MAP_HEIGHT-1:
                    m[y][x] = TILE_WALL
        return m

    def add_player(self, player_id):
        spawn = [(1,1), (1, MAP_HEIGHT-2), (MAP_WIDTH-2,1), (MAP_WIDTH-2, MAP_HEIGHT-2)]
        x,y = spawn[player_id % len(spawn)]
        self.players[player_id] = {"x": x, "y": y, "alive": True, "lives": 3}

    def move_player(self, player_id, direction):
        if player_id not in self.players or not self.players[player_id]["alive"]:
            return
        dx, dy = {"UP":(0,-1), "DOWN":(0,1), "LEFT":(-1,0), "RIGHT":(1,0)}.get(direction, (0,0))
        px, py = self.players[player_id]["x"], self.players[player_id]["y"]
        nx, ny = px + dx, py + dy
        if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT and self.map[ny][nx] == TILE_EMPTY:
            self.players[player_id]["x"], self.players[player_id]["y"] = nx, ny

    def tick(self):
        # niente logica temporale per ora
        pass

    def get_state(self):
        return {"map": self.map, "players": self.players}

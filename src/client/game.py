import pygame
import json
import threading

TILE_SIZE = 32
TILE_COLORS = {
    0: (30, 30, 30),     # empty
    1: (100, 100, 100),  # wall
    2: (150, 75, 0),     # block
    3: (255, 0, 0),      # bomb
    4: (255, 165, 0),    # fire
}

PLAYER_COLORS = [
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255)
]

class BombermanClient:
    def __init__(self, sock):
        pygame.init()
        self.sock = sock
        self.player_id = None
        self.is_spectator = False
        self.session_id = self.generate_session_id()   # ID persistente del client
        self.map_width_px = 15 * TILE_SIZE
        self.map_height_px = 13 * TILE_SIZE
        self.sidebar_width = 200

        self.screen = pygame.display.set_mode(
            (self.map_width_px + self.sidebar_width, self.map_height_px)
        )
        self.font = pygame.font.SysFont("Arial", 20)
        self.small_font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 36, bold=True)
        self.big_font = pygame.font.SysFont("Arial", 48, bold=True)
        pygame.display.set_caption("Bomberman")
        self.clock = pygame.time.Clock()
        self.state = None

        # Chat input
        self.chat_input = ""
        self.chat_active = False
        self.cursor_visible = True
        self.cursor_timer = 0


        # Colori migliorati
        self.COLORS = {
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



        threading.Thread(target=self.receive_state, daemon=True).start()

    def receive_state(self):
        buffer = ""
        while True:
            try:
                data = self.sock.recv(8192).decode()
                if not data:
                    print("Connection closed by server")
                    break

                buffer += data

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue

                    state = json.loads(line)

                    # Controlla se è una conversione da spettatore a giocatore
                    if "conversion_success" in state and state["conversion_success"]:
                        self.player_id = state["new_player_id"]
                        self.is_spectator = False
                        print(f"Converted to Player {self.player_id}")
                    elif "player_id" in state:
                        self.player_id = state["player_id"]
                        self.is_spectator = state.get("is_spectator", False)
                        print(f"Received ID: {self.player_id} (Spectator: {self.is_spectator})")
                    else:
                        self.state = state

            except Exception as e:
                print("Error receiving state:", e)
                break

    def draw_gradient_rect(self, surface, color1, color2, rect, vertical=True):
        """Disegna un rettangolo con gradiente."""
        x, y, w, h = rect
        if vertical:
            for i in range(h):
                ratio = i / h
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                pygame.draw.line(surface, (r, g, b), (x, y + i), (x + w, y + i))
        else:
            for i in range(w):
                ratio = i / w
                r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                pygame.draw.line(surface, (r, g, b), (x + i, y), (x + i, y + h))

    def draw_rounded_rect(self, surface, color, rect, radius=10):
        """Disegna un rettangolo arrotondato."""
        x, y, w, h = rect
        # Rettangoli principali
        pygame.draw.rect(surface, color, (x + radius, y, w - 2 * radius, h))
        pygame.draw.rect(surface, color, (x, y + radius, w, h - 2 * radius))
        # Angoli
        pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + radius, y + h - radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + h - radius), radius)



    def send_command(self, command):
        try:
            self.sock.sendall(command.encode())
        except:
            pass

    def run(self):
        running = True
        while running:
            self.clock.tick(30)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.send_command("UP")
                    elif event.key == pygame.K_DOWN:
                        self.send_command("DOWN")
                    elif event.key == pygame.K_LEFT:
                        self.send_command("LEFT")
                    elif event.key == pygame.K_RIGHT:
                        self.send_command("RIGHT")
                    elif event.key == pygame.K_SPACE:
                        self.send_command("BOMB")

            if self.state:
                self.draw()

        pygame.quit()

    def draw(self):
        self.screen.fill((0, 0, 0))
        if not self.state:
            return
        # Sidebar con vite
        # Sidebar con vite e stato
        x_offset = 15 * TILE_SIZE + 10
        y_offset = 10

        self.screen.fill((50, 50, 50), pygame.Rect(15 * TILE_SIZE, 0, 200, 13 * TILE_SIZE))

        for pid, pdata in self.state["players"].items():
            color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
            if pdata["alive"]:
                status = f"♥ {pdata.get('lives', 0)}"
            else:
                status = "DISCONNECTED"
            text = f"Player {pid} - {status}"
            label = self.font.render(text, True, color)
            self.screen.blit(label, (x_offset, y_offset))
            y_offset += 30


        for y, row in enumerate(self.state["map"]):
            for x, tile in enumerate(row):
                color = TILE_COLORS.get(tile, (255, 255, 255))
                pygame.draw.rect(self.screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))

        for pid, pdata in self.state["players"].items():
            if pdata["alive"]:
                color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                pygame.draw.rect(self.screen, color, (pdata["x"] * TILE_SIZE, pdata["y"] * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        for bomb in self.state.get("bombs", []):
            if bomb.get("timer", 0) > 0:  # <-- solo se la bomba è ancora attiva
                pygame.draw.rect(self.screen, TILE_COLORS[3], (bomb["x"] * TILE_SIZE, bomb["y"] * TILE_SIZE, TILE_SIZE, TILE_SIZE))

        # Mostra le esplosioni attive
        for explosion in self.state.get("explosions", []):
            for x, y in explosion["positions"]:
                pygame.draw.rect(self.screen, TILE_COLORS[4], (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))


        pygame.display.flip()

    def send_command(self, command):
        try:
            self.sock.sendall(command.encode('utf-8'))
        except:
            pass

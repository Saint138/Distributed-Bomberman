import pygame
import json
import threading
import os
import uuid
import math
import random
import time
import hashlib
import platform

TILE_SIZE = 32
TILE_COLORS = {
    0: (30, 30, 30),     # empty
    1: (100, 100, 100),  # wall
    2: (150, 75, 0),     # block
    3: (255, 0, 0),      # bomb
    4: (255, 165, 0),    # fire
}

TILE_EMPTY = 0
TILE_WALL = 1
TILE_BLOCK = 2
TILE_BOMB = 3
TILE_FIRE = 4

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
        self.player_name = None
        self.current_screen = "connecting"

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

        # Animazioni
        self.animation_timer = 0
        self.connection_timer = 0

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

        # Avvia immediatamente la connessione
        self.connect_to_server()
        threading.Thread(target=self.receive_state, daemon=True).start()

    def connect_to_server(self):
        """Invia una richiesta di connessione semplificata al server."""
        try:
            print("[CLIENT] Connecting to server...")
        except Exception as e:
            print(f"[CLIENT] Connection error: {e}")

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

                    response = json.loads(line)

                    # Gestisce risposta di join con successo
                    if "join_success" in response and response["join_success"]:
                        self.player_id = response["player_id"]
                        self.is_spectator = response.get("is_spectator", False)
                        self.player_name = response.get("player_name", "")
                        self.current_screen = "lobby"
                        print(f"[CLIENT] Successfully joined as {self.player_name}")
                        continue

                    # Controlla se è una conversione da spettatore a giocatore
                    if "conversion_success" in response and response["conversion_success"]:
                        self.player_id = response["new_player_id"]
                        self.is_spectator = False
                        print(f"[CLIENT] Converted to Player {self.player_id}")
                    else:
                        # Stato normale del gioco
                        self.state = response

            except Exception as e:
                print("Error receiving state:", e)
                break

    def send_command(self, command):
        try:
            self.sock.sendall(command.encode('utf-8'))
        except:
            pass

    def run(self):
        running = True
        while running:
            self.clock.tick(30)

            # Aggiorna il cursore lampeggiante
            self.cursor_timer += 1
            if self.cursor_timer >= 15:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

            # Aggiorna timer di connessione
            self.connection_timer += 1

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.current_screen == "connecting":
                        if event.key == pygame.K_ESCAPE:
                            running = False
                    elif self.current_screen in ["lobby", "game", "victory"]:
                        self.handle_game_input(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Click sinistro
                        self.handle_mouse_click(event.pos)

            # Renderizza la schermata appropriata
            if self.current_screen == "connecting":
                self.draw_connecting()
            elif self.state:
                if self.state.get("game_state") == "lobby":
                    self.current_screen = "lobby"
                    self.draw_lobby()
                elif self.state.get("game_state") == "playing":
                    self.current_screen = "game"
                    self.draw_game()
                elif self.state.get("game_state") == "victory":
                    self.current_screen = "victory"
                    self.draw_victory()

        pygame.quit()

    def draw_connecting(self):
        """Disegna la schermata di connessione."""
        # Sfondo gradiente
        self.draw_gradient_rect(self.screen, (20, 20, 30), (40, 40, 60),
                                (0, 0, self.screen.get_width(), self.screen.get_height()))

        # Aggiorna animazione
        self.animation_timer += 1

        # Titolo principale
        title_text = "BOMBERMAN"
        title = self.big_font.render(title_text, True, self.COLORS['text_primary'])
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 150))
        self.screen.blit(title, title_rect)

        # Messaggio di connessione animato
        dots = "." * ((self.connection_timer // 30) % 4)
        connecting_text = f"Connecting to server{dots}"
        connecting = self.font.render(connecting_text, True, self.COLORS['warning'])
        connecting_rect = connecting.get_rect(center=(self.screen.get_width() // 2, 220))
        self.screen.blit(connecting, connecting_rect)

        # Spinner di caricamento
        spinner_center = (self.screen.get_width() // 2, 280)
        spinner_radius = 20
        spinner_angle = (self.connection_timer * 5) % 360

        for i in range(8):
            angle = spinner_angle + i * 45
            end_x = spinner_center[0] + math.cos(math.radians(angle)) * spinner_radius
            end_y = spinner_center[1] + math.sin(math.radians(angle)) * spinner_radius
            alpha = 255 - (i * 30)
            color = (alpha, alpha, alpha)
            pygame.draw.circle(self.screen, color, (int(end_x), int(end_y)), 3)

        # Istruzioni
        instruction_text = "Press ESC to exit"
        instruction = self.small_font.render(instruction_text, True, self.COLORS['text_disabled'])
        instruction_rect = instruction.get_rect(center=(self.screen.get_width() // 2, 350))
        self.screen.blit(instruction, instruction_rect)

        pygame.display.flip()

    def draw_lobby(self):
        """Disegna la schermata della lobby con nomi giocatori (nasconde disconnessi)."""
        # Sfondo gradiente
        self.draw_gradient_rect(self.screen, (20, 20, 30), (40, 40, 60),
                                (0, 0, self.screen.get_width(), self.screen.get_height()))

        # Aggiorna animazione
        self.animation_timer += 1

        # Titolo con effetto glow
        title_text = "BOMBERMAN"
        if self.is_spectator:
            subtitle = "SPECTATOR MODE"
        else:
            subtitle = "LOBBY"

        # Titolo principale
        title = self.big_font.render(title_text, True, self.COLORS['text_primary'])
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 40))
        self.screen.blit(title, title_rect)

        # Sottotitolo
        subtitle_surf = self.font.render(subtitle, True, self.COLORS['warning'])
        subtitle_rect = subtitle_surf.get_rect(center=(self.screen.get_width() // 2, 70))
        self.screen.blit(subtitle_surf, subtitle_rect)

        # === PANNELLO GIOCATORI ===
        players_panel = pygame.Rect(30, 100, 330, 160)
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], players_panel)
        pygame.draw.rect(self.screen, self.COLORS['border_light'], players_panel, 3, border_radius=10)

        # Titolo pannello giocatori
        pygame.draw.circle(self.screen, self.COLORS['success'], (55, 120), 8)
        players_title = self.font.render("Players", True, self.COLORS['text_primary'])
        self.screen.blit(players_title, (70, 110))

        y_offset = 140
        connected_count = 0
        current_host = self.state.get("current_host_id", 0)

        # Mostra slot giocatori con nomi (nasconde i disconnessi)
        for i in range(4):
            player_found = False
            for pid, pdata in self.state["players"].items():
                if int(pid) == i:
                    # Skip giocatori disconnessi - non mostrarli affatto
                    if pdata.get("disconnected", False):
                        break  # Salta questo giocatore, slot apparirà vuoto

                    player_found = True
                    player_name = pdata.get("name", f"Player {pid}")

                    # Giocatore connesso
                    connected_count += 1

                    player_text = player_name
                    if int(pid) == self.player_id and not self.is_spectator:
                        player_text += " (You)"
                    if int(pid) == current_host:
                        player_text += " [HOST]"

                    label = self.font.render(player_text, True, (255, 255, 255))
                    text_width = label.get_width()

                    slot_width = max(text_width + 20, 200)
                    slot_rect = pygame.Rect(50, y_offset - 5, slot_width, 25)

                    color = PLAYER_COLORS[i]
                    pygame.draw.rect(self.screen, color, slot_rect, border_radius=5)
                    pygame.draw.rect(self.screen, self.COLORS['border_light'], slot_rect, 2, border_radius=5)

                    text_rect = label.get_rect(center=slot_rect.center)
                    self.screen.blit(label, text_rect)

                    # Indicatore host
                    if int(pid) == current_host:
                        crown_rect = pygame.Rect(slot_rect.right - 30, slot_rect.y + 2, 20, 20)
                        pygame.draw.rect(self.screen, (255, 215, 0), crown_rect, border_radius=3)
                        crown_text = self.small_font.render("H", True, (0, 0, 0))
                        crown_text_rect = crown_text.get_rect(center=crown_rect.center)
                        self.screen.blit(crown_text, crown_text_rect)
                    break

            if not player_found:
                # Slot vuoto (include giocatori disconnessi che vengono nascosti)
                slot_rect = pygame.Rect(50, y_offset - 5, 200, 25)
                pygame.draw.rect(self.screen, (40, 40, 50), slot_rect, border_radius=5)
                pygame.draw.rect(self.screen, (60, 60, 70), slot_rect, 1, border_radius=5)
                empty_text = f"Empty Slot"
                label = self.small_font.render(empty_text, True, self.COLORS['text_disabled'])
                text_rect = label.get_rect(center=slot_rect.center)
                self.screen.blit(label, text_rect)

            y_offset += 30

        # === PANNELLO CHAT ===
        chat_panel = pygame.Rect(380, 100, 280, 260)
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], chat_panel)
        pygame.draw.rect(self.screen, self.COLORS['border_light'], chat_panel, 3, border_radius=10)

        # Titolo chat
        pygame.draw.circle(self.screen, self.COLORS['warning'], (405, 120), 8)
        chat_title = self.font.render("Chat", True, self.COLORS['text_primary'])
        self.screen.blit(chat_title, (420, 110))

        # Area messaggi
        msg_area = pygame.Rect(390, 140, 260, 180)
        pygame.draw.rect(self.screen, (20, 20, 25), msg_area, border_radius=5)
        pygame.draw.rect(self.screen, self.COLORS['border'], msg_area, 1, border_radius=5)

        # Messaggi
        if "chat_messages" in self.state:
            msg_y = 145
            for msg in self.state["chat_messages"][-8:]:
                if msg_y + 20 > 315:
                    break

                if msg["is_system"]:
                    icon = "!"
                    color = self.COLORS['warning']
                    text = msg["message"][:30]
                elif msg.get("is_spectator", False):
                    icon = "S"
                    color = self.COLORS['info']
                    sender_id = msg["player_id"]
                    sender_name = "Unknown"
                    for spec_id, spec_data in self.state.get("spectators", {}).items():
                        if int(spec_id) == int(sender_id):
                            sender_name = spec_data.get("name", f"Spectator {sender_id}")
                            break
                    text = f"{sender_name}: {msg['message']}"[:30]
                else:
                    icon = "*"
                    pid = int(msg["player_id"])
                    color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                    sender_name = f"Player {pid}"
                    if str(pid) in self.state.get("players", {}):
                        sender_name = self.state["players"][str(pid)].get("name", sender_name)
                    text = f"{sender_name}: {msg['message']}"[:30]

                icon_surf = self.small_font.render(icon, True, color)
                self.screen.blit(icon_surf, (395, msg_y))
                msg_surf = self.small_font.render(text, True, self.COLORS['text_secondary'])
                self.screen.blit(msg_surf, (415, msg_y))
                msg_y += 20

        # Input chat
        input_rect = pygame.Rect(390, 325, 260, 25)
        if self.chat_active:
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.COLORS['success'], input_rect, 2, border_radius=5)

            input_text = self.small_font.render(self.chat_input, True, self.COLORS['text_primary'])
            self.screen.blit(input_text, (395, 328))

            if self.cursor_visible:
                cursor_x = 395 + input_text.get_width()
                pygame.draw.line(self.screen, self.COLORS['success'],
                                 (cursor_x, 328), (cursor_x, 345), 2)
        else:
            pygame.draw.rect(self.screen, (30, 30, 40), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.COLORS['border'], input_rect, 1, border_radius=5)
            hint = self.small_font.render("Press T to chat", True, self.COLORS['text_disabled'])
            self.screen.blit(hint, (395, 328))

        # === AREA AZIONI ===
        action_panel = pygame.Rect(100, 375, 480, 35)
        self.draw_gradient_rect(self.screen, (30, 30, 40), (40, 40, 50), action_panel)
        pygame.draw.rect(self.screen, self.COLORS['border'], action_panel, 2, border_radius=20)

        if self.is_spectator:
            if connected_count < 4:
                join_rect = pygame.Rect(240, 380, 160, 25)
                self.draw_gradient_rect(self.screen, (0, 150, 0), (0, 200, 0), join_rect)
                pygame.draw.rect(self.screen, (0, 255, 0), join_rect, 2, border_radius=12)
                join_text = self.font.render("Press J to Join", True, (255, 255, 255))
                join_rect_center = join_text.get_rect(center=join_rect.center)
                self.screen.blit(join_text, join_rect_center)
            else:
                full_text = self.font.render("All slots are full", True, self.COLORS['danger'])
                text_rect = full_text.get_rect(center=(340, 392))
                self.screen.blit(full_text, text_rect)
        elif connected_count < 2:
            wait_text = self.font.render("Waiting for players...", True, self.COLORS['text_secondary'])
            text_rect = wait_text.get_rect(center=(340, 392))
            self.screen.blit(wait_text, text_rect)
        else:
            if self.player_id == current_host:
                start_rect = pygame.Rect(240, 380, 160, 25)
                pulse = abs(math.sin(self.animation_timer * 0.05)) * 20
                color1 = (0, 150 + pulse, 0)
                color2 = (0, 200 + pulse, 0)
                self.draw_gradient_rect(self.screen, color1, color2, start_rect)
                pygame.draw.rect(self.screen, (0, 255, 0), start_rect, 2, border_radius=12)
                start_text = self.font.render("Press ENTER", True, (255, 255, 255))
                text_rect = start_text.get_rect(center=start_rect.center)
                self.screen.blit(start_text, text_rect)
            else:
                wait_text = self.font.render("Waiting for host...", True, self.COLORS['text_secondary'])
                text_rect = wait_text.get_rect(center=(340, 392))
                self.screen.blit(wait_text, text_rect)

        # Info sulla propria identità (in basso a sinistra)
        identity_text = f"You are: {self.player_name}"
        if self.is_spectator:
            identity_text += " (Spectator)"

        identity_surf = self.small_font.render(identity_text, True, self.COLORS['text_disabled'])
        self.screen.blit(identity_surf, (10, self.screen.get_height() - 25))

        pygame.display.flip()

    def draw_game(self):
        """Disegna il gioco con grafica migliorata e sidebar completa."""
        self.screen.fill(self.COLORS['bg_dark'])

        if not self.state or "map" not in self.state:
            return

        # Aggiorna animazione
        self.animation_timer += 1

        # Ombra per la griglia di gioco
        shadow_rect = pygame.Rect(5, 5, self.map_width_px, self.map_height_px)
        pygame.draw.rect(self.screen, (5, 5, 10), shadow_rect)

        # Sfondo della griglia
        pygame.draw.rect(self.screen, (20, 20, 25), (0, 0, self.map_width_px, self.map_height_px))

        # Disegna la mappa con effetti
        for y, row in enumerate(self.state["map"]):
            for x, tile in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

                if tile == TILE_EMPTY:
                    # Pavimento con pattern
                    color = (30, 30, 35) if (x + y) % 2 == 0 else (35, 35, 40)
                    pygame.draw.rect(self.screen, color, rect)
                elif tile == TILE_WALL:
                    # Muri con gradiente
                    self.draw_gradient_rect(self.screen, (80, 80, 90), (100, 100, 110), rect)
                    pygame.draw.rect(self.screen, (120, 120, 130), rect, 2)
                elif tile == TILE_BLOCK:
                    # Blocchi distruttibili con texture
                    self.draw_gradient_rect(self.screen, (150, 75, 0), (180, 95, 20), rect)
                    pygame.draw.rect(self.screen, (200, 115, 40), rect, 2)
                    # Pattern interno
                    pygame.draw.line(self.screen, (130, 65, 0),
                                     (rect.x + 5, rect.y + 5), (rect.x + 15, rect.y + 15), 2)
                    pygame.draw.line(self.screen, (130, 65, 0),
                                     (rect.x + TILE_SIZE - 5, rect.y + 5),
                                     (rect.x + TILE_SIZE - 15, rect.y + 15), 2)

        # Disegna le bombe con animazione
        for bomb in self.state.get("bombs", []):
            if bomb.get("timer", 0) > 0:
                bomb_x = bomb["x"] * TILE_SIZE + TILE_SIZE // 2
                bomb_y = bomb["y"] * TILE_SIZE + TILE_SIZE // 2

                # Pulsazione della bomba
                pulse = abs(math.sin(self.animation_timer * 0.1)) * 3
                radius = 12 + pulse

                # Ombra
                pygame.draw.circle(self.screen, (20, 0, 0), (bomb_x + 2, bomb_y + 2), radius)
                # Bomba
                pygame.draw.circle(self.screen, (60, 0, 0), (bomb_x, bomb_y), radius)
                pygame.draw.circle(self.screen, (255, 0, 0), (bomb_x, bomb_y), radius, 3)
                # Highlight
                pygame.draw.circle(self.screen, (255, 100, 100), (bomb_x - 4, bomb_y - 4), 4)

        # Disegna le esplosioni con effetto
        for explosion in self.state.get("explosions", []):
            for ex, ey in explosion["positions"]:
                rect = pygame.Rect(ex * TILE_SIZE, ey * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                # Effetto fuoco animato
                for i in range(3):
                    flame_rect = rect.inflate(-i*8, -i*8)
                    alpha = explosion["timer"] * 50
                    color = (255, 200 - i*50, 0)
                    pygame.draw.rect(self.screen, color, flame_rect)

        # Disegna i giocatori con ombra
        for pid, pdata in self.state["players"].items():
            if pdata["alive"] and not pdata.get("disconnected", False):
                player_x = pdata["x"] * TILE_SIZE
                player_y = pdata["y"] * TILE_SIZE

                # Ombra
                shadow_rect = pygame.Rect(player_x + 3, player_y + 3, TILE_SIZE - 2, TILE_SIZE - 2)
                pygame.draw.ellipse(self.screen, (10, 10, 15), shadow_rect)

                # Giocatore
                color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                player_rect = pygame.Rect(player_x + 2, player_y + 2, TILE_SIZE - 4, TILE_SIZE - 4)
                pygame.draw.rect(self.screen, color, player_rect, border_radius=8)

                # Bordo luminoso
                pygame.draw.rect(self.screen, (255, 255, 255), player_rect, 2, border_radius=8)

                # Numero giocatore
                num_text = self.small_font.render(str(pid), True, (0, 0, 0))
                num_rect = num_text.get_rect(center=player_rect.center)
                self.screen.blit(num_text, num_rect)

        # Se siamo spettatori, mostra indicatore
        if self.is_spectator:
            spec_surf = pygame.Surface((200, 30))
            spec_surf.set_alpha(200)
            spec_surf.fill((0, 0, 0))
            self.screen.blit(spec_surf, (10, 10))
            spec_text = self.font.render("SPECTATOR MODE", True, self.COLORS['warning'])
            self.screen.blit(spec_text, (20, 15))

        # === SIDEBAR MIGLIORATA ===
        sidebar_x = self.map_width_px

        # Sfondo sidebar con gradiente
        sidebar_rect = pygame.Rect(sidebar_x, 0, self.sidebar_width, self.map_height_px)
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_dark'], sidebar_rect)
        pygame.draw.line(self.screen, self.COLORS['border'], (sidebar_x, 0), (sidebar_x, self.map_height_px), 3)

        # Pannello giocatori
        y_offset = 10
        players_panel = pygame.Rect(sidebar_x + 10, y_offset, self.sidebar_width - 20, 140)
        self.draw_rounded_rect(self.screen, self.COLORS['bg_light'], players_panel)
        pygame.draw.rect(self.screen, self.COLORS['border'], players_panel, 2, border_radius=8)

        # Titolo pannello
        title_text = self.font.render("Players", True, self.COLORS['text_primary'])
        self.screen.blit(title_text, (sidebar_x + 20, y_offset + 5))

        y_offset += 30

        # Mostra tutti e 4 gli slot giocatori
        for slot_id in range(4):
            if y_offset > 130:
                break

            player_found = False
            player_name = f"Player {slot_id}"

            # Cerca il giocatore per questo slot
            for pid, pdata in self.state["players"].items():
                if int(pid) == slot_id:
                    player_found = True
                    player_name = pdata.get("name", f"Player {pid}")

                    if pdata.get("disconnected", False):
                        # Giocatore disconnesso
                        status_color = self.COLORS['text_disabled']
                        status_text = "disconnected"
                    elif not pdata["alive"] or pdata.get("lives", 0) <= 0:
                        # Giocatore eliminato
                        status_color = self.COLORS['danger']
                        status_text = "eliminated"
                    else:
                        # Giocatore vivo
                        status_color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                        hearts = "♥" * pdata.get("lives", 0)
                        status_text = hearts
                    break

            if not player_found:
                # Slot vuoto
                status_color = self.COLORS['text_disabled']
                status_text = "empty slot"
                player_name = f"Slot {slot_id}"

            # Disegna info giocatore/slot
            pygame.draw.circle(self.screen, status_color, (sidebar_x + 25, y_offset + 8), 6)
            player_text = f"{player_name}"
            player_surf = self.small_font.render(player_text, True, self.COLORS['text_primary'])
            self.screen.blit(player_surf, (sidebar_x + 35, y_offset))

            # Stato del giocatore (cuori, eliminated, disconnected, o empty)
            status_surf = self.small_font.render(status_text, True, status_color)
            self.screen.blit(status_surf, (sidebar_x + 35, y_offset + 12))

            y_offset += 30

        # Contatore spettatori
        if self.state.get("spectators"):
            spec_count = len(self.state["spectators"])
            spec_rect = pygame.Rect(sidebar_x + 10, 160, self.sidebar_width - 20, 25)
            pygame.draw.rect(self.screen, self.COLORS['bg_light'], spec_rect, border_radius=5)
            spec_text = self.small_font.render(f"👁 {spec_count} Spectators", True, self.COLORS['info'])
            self.screen.blit(spec_text, (sidebar_x + 20, 165))

        # Pannello chat
        chat_y = 200
        chat_panel = pygame.Rect(sidebar_x + 10, chat_y, self.sidebar_width - 20,
                                 self.map_height_px - chat_y - 10)
        self.draw_rounded_rect(self.screen, self.COLORS['bg_light'], chat_panel)
        pygame.draw.rect(self.screen, self.COLORS['border'], chat_panel, 2, border_radius=8)

        # Chat header
        chat_header = pygame.Rect(sidebar_x + 10, chat_y, self.sidebar_width - 20, 25)
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], chat_header)
        chat_title = self.small_font.render("💬 Chat", True, self.COLORS['text_primary'])
        self.screen.blit(chat_title, (sidebar_x + 20, chat_y + 5))

        # Messaggi
        msg_y = chat_y + 30
        if "chat_messages" in self.state:
            for msg in self.state["chat_messages"][-5:]:
                if msg_y > self.map_height_px - 50:
                    break

                if msg["is_system"]:
                    color = self.COLORS['warning']
                    text = msg["message"][:22]
                elif msg.get("is_spectator", False):
                    color = self.COLORS['info']
                    sender_id = msg["player_id"]
                    sender_name = "Unknown"
                    for spec_id, spec_data in self.state.get("spectators", {}).items():
                        if int(spec_id) == int(sender_id):
                            sender_name = spec_data.get("name", f"Spectator {sender_id}")
                            break
                    text = f"{sender_name}: {msg['message']}"[:22]
                else:
                    pid = int(msg["player_id"])
                    color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                    sender_name = f"Player {pid}"
                    if str(pid) in self.state.get("players", {}):
                        sender_name = self.state["players"][str(pid)].get("name", sender_name)
                    text = f"{sender_name}: {msg['message']}"[:22]

                msg_surf = self.small_font.render(text, True, color)
                self.screen.blit(msg_surf, (sidebar_x + 15, msg_y))
                msg_y += 18

        # Input chat
        input_y = self.map_height_px - 35
        input_rect = pygame.Rect(sidebar_x + 15, input_y, self.sidebar_width - 30, 20)

        if self.chat_active:
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.COLORS['success'], input_rect, 2, border_radius=5)
            input_text = self.small_font.render(self.chat_input[-18:], True, self.COLORS['text_primary'])
            self.screen.blit(input_text, (sidebar_x + 18, input_y + 2))

            if self.cursor_visible:
                cursor_x = sidebar_x + 18 + input_text.get_width()
                pygame.draw.line(self.screen, self.COLORS['success'],
                                 (cursor_x, input_y + 2), (cursor_x, input_y + 17), 2)
        else:
            pygame.draw.rect(self.screen, self.COLORS['bg_medium'], input_rect, border_radius=5)
            hint = self.small_font.render("T: Chat", True, self.COLORS['text_disabled'])
            self.screen.blit(hint, (sidebar_x + 18, input_y + 2))

        pygame.display.flip()

    def draw_victory(self):
        """Disegna la schermata di vittoria."""
        # Sfondo animato
        for i in range(0, self.screen.get_height(), 20):
            color_intensity = int(abs(math.sin((i + self.animation_timer) * 0.01)) * 30 + 20)
            pygame.draw.rect(self.screen, (color_intensity, color_intensity, color_intensity + 10),
                             (0, i, self.screen.get_width(), 20))

        winner_id = self.state.get("winner_id", -2)

        # Box principale
        main_box = pygame.Rect(140, 100, 400, 250)
        self.draw_gradient_rect(self.screen, (40, 40, 60), (60, 60, 80), main_box)
        pygame.draw.rect(self.screen, (255, 255, 255), main_box, 4, border_radius=20)

        # Testo vittoria
        if winner_id == -1:
            victory_text = "DRAW!"
            victory_color = self.COLORS['warning']
            sub_text = "No survivors..."
        elif winner_id >= 0:
            victory_text = f"PLAYER {winner_id}"
            victory_color = PLAYER_COLORS[winner_id % len(PLAYER_COLORS)]
            sub_text = "VICTORY!"
        else:
            victory_text = "GAME OVER"
            victory_color = self.COLORS['danger']
            sub_text = ""

        main_text = self.big_font.render(victory_text, True, (255, 255, 255))
        main_rect = main_text.get_rect(center=(340, 160))
        self.screen.blit(main_text, main_rect)

        if sub_text:
            sub_surf = self.title_font.render(sub_text, True, victory_color)
            sub_rect = sub_surf.get_rect(center=(340, 210))
            self.screen.blit(sub_surf, sub_rect)

        # Timer
        timer = self.state.get("victory_timer", 0)
        if timer > 0:
            timer_text = f"Auto-return in {timer // 10 + 1}..."
            timer_surf = self.font.render(timer_text, True, self.COLORS['text_secondary'])
            timer_rect = timer_surf.get_rect(center=(340, 250))
            self.screen.blit(timer_surf, timer_rect)

        if not self.is_spectator:
            hint_text = self.small_font.render("Press ENTER to play again", True, self.COLORS['text_secondary'])
            hint_rect = hint_text.get_rect(center=(340, 340))
            self.screen.blit(hint_text, hint_rect)

        self.animation_timer += 1
        pygame.display.flip()

    def handle_game_input(self, event):
        """Gestisce l'input durante il gioco."""
        if event.key == pygame.K_t and not self.chat_active:
            self.chat_active = True
            self.chat_input = ""
        elif self.chat_active:
            if event.key == pygame.K_RETURN:
                if self.chat_input.strip():
                    self.send_command(f"CHAT:{self.chat_input}")
                self.chat_input = ""
                self.chat_active = False
            elif event.key == pygame.K_ESCAPE:
                self.chat_input = ""
                self.chat_active = False
            elif event.key == pygame.K_BACKSPACE:
                self.chat_input = self.chat_input[:-1]
            else:
                if event.unicode and len(self.chat_input) < 45:
                    self.chat_input += event.unicode
        elif not self.chat_active:
            if self.current_screen == "lobby":
                self.handle_lobby_input(event)
            elif self.current_screen == "game":
                self.handle_game_play_input(event)
            elif self.current_screen == "victory":
                self.handle_victory_input(event)

    def handle_lobby_input(self, event):
        """Gestisce input specifici della lobby."""
        if self.is_spectator:
            if event.key == pygame.K_j:
                connected_count = sum(1 for p in self.state["players"].values()
                                      if not p.get("disconnected", False))
                if connected_count < 4:
                    self.send_command("JOIN_GAME")
        else:
            current_host = self.state.get("current_host_id", 0)
            if event.key == pygame.K_RETURN and self.player_id == current_host:
                if self.state.get("can_start", False):
                    self.send_command("START_GAME")

    def handle_game_play_input(self, event):
        """Gestisce input durante la partita."""
        if not self.is_spectator and self.state.get("game_state") == "playing":
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

    def handle_victory_input(self, event):
        """Gestisce input nella schermata vittoria."""
        if not self.is_spectator and event.key == pygame.K_RETURN:
            self.send_command("PLAY_AGAIN")

    def handle_mouse_click(self, pos):
        """Gestisce i click del mouse."""
        pass
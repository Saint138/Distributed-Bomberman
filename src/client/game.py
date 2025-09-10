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
        self.session_id = self.generate_session_id()
        self.player_name = None
        self.current_screen = "name_entry"
        self.name_input = ""
        self.name_input_active = True
        self.join_error_message = ""
        self.error_timer = 0

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

    def generate_session_id(self):
        """Genera un ID di sessione semplice."""
        try:
            pid = os.getpid()
            timestamp = time.time()
            hostname = platform.node()
            session_data = f"{pid}_{timestamp}_{hostname}_{random.randint(1000, 9999)}"
            session_id = hashlib.sha256(session_data.encode()).hexdigest()[:16]
            print(f"[SESSION] Generated session ID: {session_id}")
            return session_id
        except Exception as e:
            print(f"[SESSION] Error: {e}, using UUID")
            return str(uuid.uuid4())[:16]

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

                    # Gestisce errori di join
                    if "error" in response:
                        error_type = response["error"]
                        details = response.get("details", "")

                        if error_type == "name_taken":
                            if details:
                                self.show_error(f"Nome già in uso: {details}")
                            else:
                                self.show_error("Nome già in uso!")
                        elif error_type == "name_too_short":
                            self.show_error("Nome troppo corto!")
                        elif error_type == "invalid_request":
                            self.show_error("Richiesta non valida!")
                        elif error_type == "session_mismatch":
                            self.show_error("Errore sessione!")
                        elif error_type == "server_error":
                            self.show_error("Errore del server!")
                        else:
                            self.show_error("Errore sconosciuto!")
                        continue

                    # Gestisce risposta di join con successo
                    if "join_success" in response and response["join_success"]:
                        self.player_id = response["player_id"]
                        self.is_spectator = response.get("is_spectator", False)
                        self.player_name = response.get("player_name", "")
                        self.current_screen = "lobby"
                        print(f"Successfully joined as {self.player_name}")
                        continue

                    # Controlla se è una conversione da spettatore a giocatore
                    if "conversion_success" in response and response["conversion_success"]:
                        self.player_id = response["new_player_id"]
                        self.is_spectator = False
                        print(f"Converted to Player {self.player_id}")
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

            # Aggiorna timer errori
            if self.error_timer > 0:
                self.error_timer -= 1
                if self.error_timer <= 0:
                    self.join_error_message = ""

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.current_screen == "name_entry":
                        self.handle_name_entry_input(event)
                    elif self.current_screen in ["lobby", "game", "victory"]:
                        self.handle_game_input(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Click sinistro
                        self.handle_mouse_click(event.pos)

            # Renderizza la schermata appropriata
            if self.current_screen == "name_entry":
                self.draw_name_entry()
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

    def draw_name_entry(self):
        """Disegna la schermata di inserimento nome e spiegazione del gioco."""
        # Sfondo gradiente
        self.draw_gradient_rect(self.screen, (20, 20, 30), (40, 40, 60),
                                (0, 0, self.screen.get_width(), self.screen.get_height()))

        # Aggiorna animazione
        self.animation_timer += 1

        # Titolo principale
        title_text = "BOMBERMAN"
        title = self.big_font.render(title_text, True, self.COLORS['text_primary'])
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 40))
        self.screen.blit(title, title_rect)

        # Welcome subtitle
        welcome_text = "Welcome to Bomberman!"
        welcome = self.font.render(welcome_text, True, self.COLORS['warning'])
        welcome_rect = welcome.get_rect(center=(self.screen.get_width() // 2, 75))
        self.screen.blit(welcome, welcome_rect)

        # Spiegazione del gioco con spaziatura corretta
        current_y = 110

        # HOW TO PLAY section
        how_to_play_title = self.font.render("HOW TO PLAY:", True, self.COLORS['warning'])
        how_to_play_rect = how_to_play_title.get_rect(center=(self.screen.get_width() // 2, current_y))
        self.screen.blit(how_to_play_title, how_to_play_rect)
        current_y += 30

        game_rules = [
            "• Move with arrow keys",
            "• Place bombs with SPACEBAR",
            "• Destroy blocks and eliminate opponents",
            "• Last player standing wins!"
        ]

        for rule in game_rules:
            rule_text = self.small_font.render(rule, True, self.COLORS['text_secondary'])
            rule_rect = rule_text.get_rect(center=(self.screen.get_width() // 2, current_y))
            self.screen.blit(rule_text, rule_rect)
            current_y += 20

        current_y += 20  # Spazio extra tra sezioni

        # === SEZIONE NOME ===
        # Box per inserimento nome con bordo evidenziato
        name_box = pygame.Rect(150, current_y, 380, 50)

        # Ombra del box
        shadow_box = name_box.copy()
        shadow_box.x += 3
        shadow_box.y += 3
        self.draw_rounded_rect(self.screen, (10, 10, 15), shadow_box, radius=15)

        # Box principale con gradiente
        self.draw_gradient_rect(self.screen, self.COLORS['bg_light'], self.COLORS['bg_medium'], name_box)

        # Bordo animato se attivo
        if self.name_input_active:
            pulse = abs(math.sin(self.animation_timer * 0.05)) * 20
            border_color = (100 + pulse, 200 + pulse, 100 + pulse)
            pygame.draw.rect(self.screen, border_color, name_box, 3, border_radius=15)
        else:
            pygame.draw.rect(self.screen, self.COLORS['border'], name_box, 2, border_radius=15)

        # Label per inserimento nome (sopra il box)
        label = self.font.render("Enter your name (2-20 characters):", True, self.COLORS['text_primary'])
        label_rect = label.get_rect(center=(self.screen.get_width() // 2, current_y - 25))
        self.screen.blit(label, label_rect)

        # Input nome centrato nel box
        if self.name_input:
            name_text = self.font.render(self.name_input, True, self.COLORS['text_primary'])
        else:
            # Placeholder text
            name_text = self.font.render("Type your name here...", True, self.COLORS['text_disabled'])

        name_rect = name_text.get_rect(center=name_box.center)
        self.screen.blit(name_text, name_rect)

        # Cursore solo se c'è del testo
        if self.cursor_visible and self.name_input_active and self.name_input:
            cursor_x = name_rect.right + 5
            cursor_y = name_box.centery
            pygame.draw.line(self.screen, self.COLORS['success'],
                             (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 3)

        current_y += 80

        # Pulsante Join (più grande e centrato)
        join_button = pygame.Rect(240, current_y, 200, 45)

        # Determina se il pulsante è attivo
        button_active = len(self.name_input.strip()) >= 2

        if button_active:
            # Pulsante attivo con animazione
            pulse = abs(math.sin(self.animation_timer * 0.08)) * 15
            button_color1 = (50 + pulse, 200 + pulse, 50 + pulse)
            button_color2 = (30 + pulse, 150 + pulse, 30 + pulse)
            border_color = (100, 255, 100)
        else:
            # Pulsante disattivato
            button_color1 = self.COLORS['text_disabled']
            button_color2 = (80, 80, 80)
            border_color = self.COLORS['border']

        # Ombra pulsante
        shadow_button = join_button.copy()
        shadow_button.x += 3
        shadow_button.y += 3
        self.draw_rounded_rect(self.screen, (10, 10, 15), shadow_button, radius=20)

        # Pulsante
        self.draw_gradient_rect(self.screen, button_color1, button_color2, join_button)
        pygame.draw.rect(self.screen, border_color, join_button, 3, border_radius=20)

        # Testo pulsante
        join_text = self.title_font.render("JOIN LOBBY", True, self.COLORS['text_primary'])
        join_rect = join_text.get_rect(center=join_button.center)
        self.screen.blit(join_text, join_rect)

        current_y += 70

        # Istruzioni chiare
        instructions = [
            "• Type your name and press ENTER",
            "• Or click JOIN LOBBY button",
            "• Press ESC to exit"
        ]

        for instruction in instructions:
            inst_text = self.small_font.render(instruction, True, self.COLORS['info'])
            inst_rect = inst_text.get_rect(center=(self.screen.get_width() // 2, current_y))
            self.screen.blit(inst_text, inst_rect)
            current_y += 20

        current_y += 20

        # Messaggio di errore (solo se presente)
        if self.join_error_message:
            # Box errore
            error_box = pygame.Rect(100, current_y, 480, 35)
            pygame.draw.rect(self.screen, (60, 20, 20), error_box, border_radius=10)
            pygame.draw.rect(self.screen, self.COLORS['danger'], error_box, 2, border_radius=10)

            error_text = self.font.render(self.join_error_message, True, self.COLORS['danger'])
            error_rect = error_text.get_rect(center=error_box.center)
            self.screen.blit(error_text, error_rect)

        pygame.display.flip()

    def draw_lobby(self):
        """Disegna la schermata della lobby con nomi giocatori."""
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

        # Pulsante X per uscire (solo per giocatori, non spettatori)
        if not self.is_spectator:
            exit_button = pygame.Rect(330, 110, 25, 25)
            pulse = abs(math.sin(self.animation_timer * 0.03)) * 10
            exit_color = (200 + int(pulse), 50, 50)

            pygame.draw.rect(self.screen, exit_color, exit_button, border_radius=5)
            pygame.draw.rect(self.screen, (255, 100, 100), exit_button, 2, border_radius=5)

            # X centrata
            x_text = self.font.render("X", True, (255, 255, 255))
            x_rect = x_text.get_rect(center=exit_button.center)
            self.screen.blit(x_text, x_rect)

        # Titolo pannello giocatori
        pygame.draw.circle(self.screen, self.COLORS['success'], (55, 120), 8)
        players_title = self.font.render("Players", True, self.COLORS['text_primary'])
        self.screen.blit(players_title, (70, 110))

        y_offset = 140
        connected_count = 0
        current_host = self.state.get("current_host_id", 0)

        # Mostra slot giocatori con nomi
        for i in range(4):
            player_found = False
            for pid, pdata in self.state["players"].items():
                if int(pid) == i:
                    player_found = True
                    player_name = pdata.get("name", f"Player {pid}")

                    if pdata.get("disconnected", False):
                        # Giocatore disconnesso - mostra timer
                        disconnect_time_left = pdata.get("disconnect_time_left", 0)
                        temp_away = pdata.get("temporarily_away", False)

                        if temp_away:
                            player_text = f"{player_name} - Away ({disconnect_time_left}s)"
                        else:
                            player_text = f"{player_name} - Reconnecting ({disconnect_time_left}s)"

                        label = self.font.render(player_text, True, self.COLORS['text_disabled'])
                        text_width = label.get_width()

                        slot_width = max(text_width + 20, 280)
                        slot_rect = pygame.Rect(50, y_offset - 5, slot_width, 25)

                        if temp_away:
                            slot_color = (80, 80, 120) if disconnect_time_left > 10 else (120, 80, 100)
                        else:
                            slot_color = (100, 100, 50) if disconnect_time_left > 10 else (150, 50, 50)

                        pygame.draw.rect(self.screen, slot_color, slot_rect, border_radius=5)
                        pygame.draw.rect(self.screen, self.COLORS['border'], slot_rect, 2, border_radius=5)

                        text_rect = label.get_rect(center=slot_rect.center)
                        self.screen.blit(label, text_rect)

                        # Barra di progresso del timer
                        progress_width = int((disconnect_time_left / 20.0) * (slot_width - 10))
                        if progress_width > 0:
                            progress_rect = pygame.Rect(slot_rect.x + 5, slot_rect.bottom - 5, progress_width, 3)
                            progress_color = self.COLORS['info'] if temp_away else self.COLORS['warning']
                            pygame.draw.rect(self.screen, progress_color, progress_rect)
                    else:
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
                # Slot vuoto
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
            wait_text = self.font.render("Waiting for players... (X: Leave)", True, self.COLORS['text_secondary'])
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
                wait_text = self.font.render("Waiting for host... (X: Leave)", True, self.COLORS['text_secondary'])
                text_rect = wait_text.get_rect(center=(340, 392))
                self.screen.blit(wait_text, text_rect)

        pygame.display.flip()

    def draw_game(self):
        """Disegna il gioco."""
        self.screen.fill(self.COLORS['bg_dark'])

        if not self.state or "map" not in self.state:
            return

        self.animation_timer += 1

        # Disegna la mappa
        for y, row in enumerate(self.state["map"]):
            for x, tile in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

                if tile == TILE_EMPTY:
                    color = (30, 30, 35) if (x + y) % 2 == 0 else (35, 35, 40)
                    pygame.draw.rect(self.screen, color, rect)
                elif tile == TILE_WALL:
                    self.draw_gradient_rect(self.screen, (80, 80, 90), (100, 100, 110), rect)
                    pygame.draw.rect(self.screen, (120, 120, 130), rect, 2)
                elif tile == TILE_BLOCK:
                    self.draw_gradient_rect(self.screen, (150, 75, 0), (180, 95, 20), rect)
                    pygame.draw.rect(self.screen, (200, 115, 40), rect, 2)

        # Disegna le bombe
        for bomb in self.state.get("bombs", []):
            if bomb.get("timer", 0) > 0:
                bomb_x = bomb["x"] * TILE_SIZE + TILE_SIZE // 2
                bomb_y = bomb["y"] * TILE_SIZE + TILE_SIZE // 2
                pulse = abs(math.sin(self.animation_timer * 0.1)) * 3
                radius = 12 + pulse
                pygame.draw.circle(self.screen, (255, 0, 0), (bomb_x, bomb_y), radius)

        # Disegna le esplosioni
        for explosion in self.state.get("explosions", []):
            for ex, ey in explosion["positions"]:
                rect = pygame.Rect(ex * TILE_SIZE, ey * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, (255, 200, 0), rect)

        # Disegna i giocatori
        for pid, pdata in self.state["players"].items():
            if pdata["alive"] and not pdata.get("disconnected", False):
                player_x = pdata["x"] * TILE_SIZE
                player_y = pdata["y"] * TILE_SIZE
                color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                player_rect = pygame.Rect(player_x + 2, player_y + 2, TILE_SIZE - 4, TILE_SIZE - 4)
                pygame.draw.rect(self.screen, color, player_rect, border_radius=8)

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

    def attempt_join_lobby(self):
        """Tenta di entrare nella lobby con il nome specificato."""
        self.player_name = self.name_input.strip()
        if len(self.player_name) < 2:
            self.show_error("Nome troppo corto (minimo 2 caratteri)")
            return

        try:
            # Invia handshake di sessione
            session_handshake = json.dumps({
                "type": "session_handshake",
                "session_id": self.session_id,
                "timestamp": time.time(),
                "platform": platform.system()
            })
            self.sock.sendall((session_handshake + "\n").encode())

            time.sleep(0.1)  # Breve pausa

            # Invia richiesta di join
            join_request = json.dumps({
                "type": "join_request",
                "session_id": self.session_id,
                "player_name": self.player_name,
                "timestamp": time.time()
            })
            self.sock.sendall((join_request + "\n").encode())
            print(f"[CLIENT] Attempting to join with name: {self.player_name}")
        except Exception as e:
            self.show_error("Errore di connessione")
            print(f"Error joining: {e}")

    def handle_name_entry_input(self, event):
        """Gestisce l'input nella schermata di inserimento nome."""
        if self.name_input_active:
            if event.key == pygame.K_RETURN:
                if len(self.name_input.strip()) >= 2:
                    self.attempt_join_lobby()
                else:
                    self.show_error("Nome troppo corto (minimo 2 caratteri)")
            elif event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                exit()
            else:
                if event.unicode and len(self.name_input) < 20 and event.unicode.isprintable():
                    self.name_input += event.unicode

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
        elif (event.key == pygame.K_x and
              self.current_screen == "lobby" and
              not self.is_spectator and
              not self.chat_active):
            self.send_command("LEAVE_TEMPORARILY")
            self.return_to_name_entry()
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

    def show_error(self, message):
        """Mostra un messaggio di errore temporaneo."""
        self.join_error_message = message
        self.error_timer = 90

    def return_to_name_entry(self):
        """Torna alla schermata di inserimento nome."""
        self.current_screen = "name_entry"
        self.name_input = self.player_name or ""
        self.name_input_active = True
        self.join_error_message = ""
        self.state = None

    def handle_mouse_click(self, pos):
        """Gestisce i click del mouse."""
        mouse_x, mouse_y = pos

        if self.current_screen == "lobby" and not self.is_spectator:
            exit_button = pygame.Rect(330, 110, 25, 25)
            if exit_button.collidepoint(mouse_x, mouse_y):
                self.send_command("LEAVE_TEMPORARILY")
                self.return_to_name_entry()

        elif self.current_screen == "name_entry":
            join_button = pygame.Rect(240, 320, 200, 45)
            if join_button.collidepoint(mouse_x, mouse_y) and len(self.name_input.strip()) >= 2:
                self.attempt_join_lobby()

            name_box = pygame.Rect(150, 240, 380, 50)
            if name_box.collidepoint(mouse_x, mouse_y):
                self.name_input_active = True
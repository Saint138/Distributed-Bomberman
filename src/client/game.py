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

        # NON inviare handshake automaticamente - aspettiamo il nome
        threading.Thread(target=self.receive_state, daemon=True).start()

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

    def draw_lobby(self):
        """Disegna la schermata della lobby con grafica migliorata, nomi giocatori e pulsante X."""
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

        # Effetto glow per il titolo
        glow_size = abs(math.sin(self.animation_timer * 0.02)) * 5
        for i in range(3):
            alpha = 50 - i * 15
            glow_color = (255, 200, 100, alpha)
            title_glow = self.big_font.render(title_text, True, glow_color)
            title_rect = title_glow.get_rect(center=(self.screen.get_width() // 2, 40))
            title_rect.x += (i - 1) * 2
            title_rect.y += (i - 1) * 2
            self.screen.blit(title_glow, title_rect)

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
        # Ombra
        shadow_rect = players_panel.copy()
        shadow_rect.x += 5
        shadow_rect.y += 5
        self.draw_rounded_rect(self.screen, (10, 10, 15), shadow_rect)
        # Pannello principale
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], players_panel)
        pygame.draw.rect(self.screen, self.COLORS['border_light'], players_panel, 3, border_radius=10)

        # Pulsante X per uscire (solo per giocatori, non spettatori) - COORDINATE CORRETTE
        if not self.is_spectator:
            exit_button = pygame.Rect(330, 110, 25, 25)  # Spostato più a sinistra
            # Effetto hover simulato con animazione
            pulse = abs(math.sin(self.animation_timer * 0.03)) * 10
            exit_color = (200 + int(pulse), 50, 50)

            pygame.draw.rect(self.screen, exit_color, exit_button, border_radius=5)
            pygame.draw.rect(self.screen, (255, 100, 100), exit_button, 2, border_radius=5)

            # X bianca centrata - USA CARATTERE ASCII
            x_text = self.font.render("X", True, (255, 255, 255))
            x_rect = x_text.get_rect(center=exit_button.center)
            self.screen.blit(x_text, x_rect)

            # Tooltip per il pulsante X (spostato anche questo)
            tooltip = self.small_font.render("Leave", True, self.COLORS['text_disabled'])
            self.screen.blit(tooltip, (315, 140))  # Spostato più a sinistra

        # Icona giocatori e titolo
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

                        # Calcola la larghezza necessaria per il testo
                        label = self.font.render(player_text, True, self.COLORS['text_disabled'])
                        text_width = label.get_width()

                        # Adatta la larghezza del rettangolo al testo con padding
                        slot_width = max(text_width + 20, 280)
                        slot_rect = pygame.Rect(50, y_offset - 5, slot_width, 25)

                        # Slot disconnesso - colore basato sul tempo rimanente e tipo
                        if temp_away:
                            if disconnect_time_left > 15:
                                slot_color = (80, 80, 120)  # Blu scuro per away
                            elif disconnect_time_left > 10:
                                slot_color = (100, 80, 120)
                            elif disconnect_time_left > 5:
                                slot_color = (120, 80, 100)
                            else:
                                slot_color = (140, 80, 80)
                        else:
                            # Reconnecting
                            if disconnect_time_left > 15:
                                slot_color = (100, 100, 50)  # Giallo scuro
                            elif disconnect_time_left > 10:
                                slot_color = (120, 100, 50)
                            elif disconnect_time_left > 5:
                                slot_color = (150, 100, 50)  # Arancione
                            else:
                                slot_color = (150, 50, 50)  # Rosso scuro

                        pygame.draw.rect(self.screen, slot_color, slot_rect, border_radius=5)
                        pygame.draw.rect(self.screen, self.COLORS['border'], slot_rect, 2, border_radius=5)

                        # Testo centrato
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

                        # Prepara il testo del giocatore
                        player_text = player_name
                        if int(pid) == self.player_id and not self.is_spectator:
                            player_text += " (You)"
                        if int(pid) == current_host:
                            player_text += " [HOST]"  # Sostituisce la corona con [HOST]

                        # Calcola la larghezza necessaria per il testo
                        label = self.font.render(player_text, True, (255, 255, 255))
                        text_width = label.get_width()

                        # Adatta la larghezza del rettangolo al testo con padding
                        slot_width = max(text_width + 20, 200)
                        slot_rect = pygame.Rect(50, y_offset - 5, slot_width, 25)

                        # Slot occupato - con colore del giocatore
                        color = PLAYER_COLORS[i]
                        pygame.draw.rect(self.screen, color, slot_rect, border_radius=5)
                        pygame.draw.rect(self.screen, self.COLORS['border_light'], slot_rect, 2, border_radius=5)

                        # Testo giocatore centrato nel rettangolo
                        text_rect = label.get_rect(center=slot_rect.center)
                        self.screen.blit(label, text_rect)

                        # Se è l'host, aggiungi un piccolo indicatore visivo
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

        # === PANNELLO SPETTATORI ===
        if self.state.get("spectators"):
            spec_panel = pygame.Rect(30, 270, 330, 90)
            self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], spec_panel)
            pygame.draw.rect(self.screen, self.COLORS['border'], spec_panel, 2, border_radius=8)

            # Icona spettatori
            pygame.draw.circle(self.screen, self.COLORS['info'], (55, 285), 6)
            spec_title = self.font.render("Spectators", True, self.COLORS['text_secondary'])
            self.screen.blit(spec_title, (70, 275))

            y_offset = 300
            spectator_count = 0
            for spec_id, spec_data in self.state["spectators"].items():
                if spectator_count >= 2:
                    remaining = len(self.state["spectators"]) - 2
                    if remaining > 0:
                        more_text = f"... +{remaining} more"
                        label = self.small_font.render(more_text, True, self.COLORS['text_disabled'])
                        self.screen.blit(label, (60, y_offset))
                    break

                spec_name = spec_data.get("name", f"Spectator {spec_id}")
                spec_text = spec_name
                if int(spec_id) == self.player_id and self.is_spectator:
                    spec_text += " (You)"

                label = self.small_font.render(spec_text, True, self.COLORS['text_secondary'])
                self.screen.blit(label, (60, y_offset))
                y_offset += 20
                spectator_count += 1

        # === PANNELLO CHAT ===
        chat_panel = pygame.Rect(380, 100, 280, 260)
        # Ombra
        shadow_rect = chat_panel.copy()
        shadow_rect.x += 5
        shadow_rect.y += 5
        self.draw_rounded_rect(self.screen, (10, 10, 15), shadow_rect)
        # Pannello principale
        self.draw_gradient_rect(self.screen, self.COLORS['bg_medium'], self.COLORS['bg_light'], chat_panel)
        pygame.draw.rect(self.screen, self.COLORS['border_light'], chat_panel, 3, border_radius=10)

        # Icona chat
        pygame.draw.circle(self.screen, self.COLORS['warning'], (405, 120), 8)
        chat_title = self.font.render("Chat", True, self.COLORS['text_primary'])
        self.screen.blit(chat_title, (420, 110))

        # Area messaggi con sfondo
        msg_area = pygame.Rect(390, 140, 260, 180)
        pygame.draw.rect(self.screen, (20, 20, 25), msg_area, border_radius=5)
        pygame.draw.rect(self.screen, self.COLORS['border'], msg_area, 1, border_radius=5)

        # Messaggi con caratteri ASCII
        if "chat_messages" in self.state:
            msg_y = 145
            for msg in self.state["chat_messages"][-8:]:
                if msg_y + 20 > 315:
                    break

                if msg["is_system"]:
                    icon = "!"  # Sostituisce il fulmine
                    color = self.COLORS['warning']
                    text = msg["message"][:30]
                elif msg.get("is_spectator", False):
                    icon = "S"  # Sostituisce l'occhio
                    color = self.COLORS['info']
                    # Mostra il nome dello spettatore se disponibile
                    sender_id = msg["player_id"]
                    sender_name = "Unknown"
                    for spec_id, spec_data in self.state.get("spectators", {}).items():
                        if int(spec_id) == int(sender_id):
                            sender_name = spec_data.get("name", f"Spectator {sender_id}")
                            break
                    text = f"{sender_name}: {msg['message']}"[:30]
                else:
                    icon = "*"  # Sostituisce il fumetto
                    pid = int(msg["player_id"])
                    color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                    # Mostra il nome del giocatore se disponibile
                    sender_name = f"Player {pid}"
                    if str(pid) in self.state.get("players", {}):
                        sender_name = self.state["players"][str(pid)].get("name", sender_name)
                    text = f"{sender_name}: {msg['message']}"[:30]

                # Icona e testo
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
                # Pulsante per unirsi
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
                # Pulsante start con animazione
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

        # Info sulla propria identità (in basso a sinistra)
        identity_text = ""
        if self.is_spectator:
            identity_text = f"You are: {self.player_name} (Spectator)"
        else:
            identity_text = f"You are: {self.player_name} (Player {self.player_id})"

        identity_surf = self.small_font.render(identity_text, True, self.COLORS['text_disabled'])
        self.screen.blit(identity_surf, (10, self.screen.get_height() - 25))

        # Controlli rapidi (in basso a destra)
        if not self.is_spectator:
            controls_text = "T: Chat | X: Leave | ENTER: Start (if host)"
        else:
            controls_text = "T: Chat | J: Join as Player"

        controls_surf = self.small_font.render(controls_text, True, self.COLORS['text_disabled'])
        controls_rect = controls_surf.get_rect()
        controls_rect.bottomright = (self.screen.get_width() - 10, self.screen.get_height() - 5)
        self.screen.blit(controls_surf, controls_rect)

        pygame.display.flip()

    def draw_game(self):
        """Disegna il gioco con grafica migliorata."""
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
        players_panel = pygame.Rect(sidebar_x + 10, y_offset, self.sidebar_width - 20, 120)
        self.draw_rounded_rect(self.screen, self.COLORS['bg_light'], players_panel)
        pygame.draw.rect(self.screen, self.COLORS['border'], players_panel, 2, border_radius=8)

        # Titolo pannello
        title_text = self.font.render("Players", True, self.COLORS['text_primary'])
        self.screen.blit(title_text, (sidebar_x + 20, y_offset + 5))

        y_offset += 30
        for pid, pdata in self.state["players"].items():
            if y_offset > 110:
                break

            # Determina lo stato del giocatore
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

            # Disegna info giocatore
            pygame.draw.circle(self.screen, status_color, (sidebar_x + 25, y_offset + 8), 6)
            player_text = f"P{pid}"
            player_surf = self.small_font.render(player_text, True, self.COLORS['text_primary'])
            self.screen.blit(player_surf, (sidebar_x + 35, y_offset))

            # Stato del giocatore (cuori, eliminated, o disconnected)
            status_font = self.small_font if status_text in ["eliminated", "disconnected"] else self.small_font
            status_surf = status_font.render(status_text, True, status_color)
            self.screen.blit(status_surf, (sidebar_x + 65, y_offset))

            y_offset += 22

        # Contatore spettatori
        if self.state.get("spectators"):
            spec_count = len(self.state["spectators"])
            spec_rect = pygame.Rect(sidebar_x + 10, 140, self.sidebar_width - 20, 25)
            pygame.draw.rect(self.screen, self.COLORS['bg_light'], spec_rect, border_radius=5)
            spec_text = self.small_font.render(f"👁 {spec_count} Spectators", True, self.COLORS['info'])
            self.screen.blit(spec_text, (sidebar_x + 20, 145))

        # Pannello chat
        chat_y = 180
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
            for msg in self.state["chat_messages"][-6:]:
                if msg_y > self.map_height_px - 50:
                    break

                if msg["is_system"]:
                    color = self.COLORS['warning']
                    text = msg["message"][:22]
                elif msg.get("is_spectator", False):
                    color = self.COLORS['info']
                    text = f"S{msg['player_id']}: {msg['message']}"[:22]
                else:
                    pid = int(msg["player_id"])
                    color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                    text = f"P{pid}: {msg['message']}"[:22]

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
        """Disegna la schermata di vittoria con effetti speciali."""
        # Sfondo animato
        for i in range(0, self.screen.get_height(), 20):
            color_intensity = int(abs(math.sin((i + self.animation_timer) * 0.01)) * 30 + 20)
            pygame.draw.rect(self.screen, (color_intensity, color_intensity, color_intensity + 10),
                             (0, i, self.screen.get_width(), 20))

        # Overlay semi-trasparente
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 10))
        self.screen.blit(overlay, (0, 0))

        # Particelle di vittoria
        for i in range(20):
            x = random.randint(0, self.screen.get_width())
            y = (self.animation_timer * 2 + i * 50) % self.screen.get_height()
            size = random.randint(2, 5)
            color = random.choice([self.COLORS['warning'], self.COLORS['success'], (255, 255, 255)])
            pygame.draw.circle(self.screen, color, (x, y), size)

        # Determina il vincitore
        winner_id = self.state.get("winner_id", -2)

        # Box principale
        main_box = pygame.Rect(140, 100, 400, 250)
        # Ombra
        shadow_box = main_box.copy()
        shadow_box.x += 10
        shadow_box.y += 10
        self.draw_rounded_rect(self.screen, (5, 5, 10), shadow_box, radius=20)

        # Box con gradiente
        self.draw_gradient_rect(self.screen, (40, 40, 60), (60, 60, 80), main_box)

        # Bordo luminoso animato
        border_color = (
            int(abs(math.sin(self.animation_timer * 0.05)) * 100 + 155),
            int(abs(math.sin(self.animation_timer * 0.05 + 1)) * 100 + 155),
            int(abs(math.sin(self.animation_timer * 0.05 + 2)) * 100 + 155)
        )
        pygame.draw.rect(self.screen, border_color, main_box, 4, border_radius=20)

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

        # Effetto glow per il testo principale
        for i in range(5):
            glow_surf = self.big_font.render(victory_text, True, victory_color)
            glow_surf.set_alpha(50 - i * 10)
            glow_rect = glow_surf.get_rect(center=(340 + i*2, 160 + i*2))
            self.screen.blit(glow_surf, glow_rect)

        # Testo principale
        main_text = self.big_font.render(victory_text, True, (255, 255, 255))
        main_rect = main_text.get_rect(center=(340, 160))
        self.screen.blit(main_text, main_rect)

        # Sottotitolo
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

        # Pulsante Play Again
        if not self.is_spectator:
            button_rect = pygame.Rect(270, 290, 140, 40)
            # Animazione pulsante
            pulse = abs(math.sin(self.animation_timer * 0.05)) * 10
            button_color1 = (0, 150 + pulse, 0)
            button_color2 = (0, 200 + pulse, 0)

            # Ombra pulsante
            shadow_rect = button_rect.copy()
            shadow_rect.x += 3
            shadow_rect.y += 3
            self.draw_rounded_rect(self.screen, (10, 10, 15), shadow_rect, radius=20)

            # Pulsante
            self.draw_gradient_rect(self.screen, button_color1, button_color2, button_rect)
            pygame.draw.rect(self.screen, (0, 255, 0), button_rect, 3, border_radius=20)

            # Testo pulsante
            button_text = self.font.render("Play Again", True, (255, 255, 255))
            text_rect = button_text.get_rect(center=button_rect.center)
            self.screen.blit(button_text, text_rect)

            hint_text = self.small_font.render("Press ENTER", True, self.COLORS['text_secondary'])
            hint_rect = hint_text.get_rect(center=(340, 340))
            self.screen.blit(hint_text, hint_rect)
        else:
            spec_text = self.font.render("Waiting for players...", True, self.COLORS['text_secondary'])
            spec_rect = spec_text.get_rect(center=(340, 310))
            self.screen.blit(spec_text, spec_rect)

        # Chat box in basso
        chat_box = pygame.Rect(70, 370, 540, 100)
        self.draw_rounded_rect(self.screen, self.COLORS['bg_medium'], chat_box)
        pygame.draw.rect(self.screen, self.COLORS['border'], chat_box, 2, border_radius=10)

        # Messaggi chat
        if "chat_messages" in self.state:
            msg_y = 380
            for msg in self.state["chat_messages"][-4:]:
                if msg["is_system"]:
                    color = self.COLORS['warning']
                    text = msg["message"]
                elif msg.get("is_spectator", False):
                    color = self.COLORS['info']
                    text = f"S{msg['player_id']}: {msg['message']}"
                else:
                    pid = int(msg["player_id"])
                    color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                    text = f"P{pid}: {msg['message']}"

                msg_surf = self.small_font.render(text[:60], True, color)
                self.screen.blit(msg_surf, (80, msg_y))
                msg_y += 20

        # Input chat
        if self.chat_active:
            input_rect = pygame.Rect(75, 450, 530, 25)
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.COLORS['success'], input_rect, 2, border_radius=5)

            input_text = self.small_font.render(self.chat_input, True, self.COLORS['text_primary'])
            self.screen.blit(input_text, (80, 453))

            if self.cursor_visible:
                cursor_x = 80 + input_text.get_width()
                pygame.draw.line(self.screen, self.COLORS['success'],
                                 (cursor_x, 453), (cursor_x, 470), 2)
        else:
            hint = self.small_font.render("Press T to chat", True, self.COLORS['text_disabled'])
            self.screen.blit(hint, (80, 453))

        # Aggiorna animazione
        self.animation_timer += 1

        pygame.display.flip()

    def draw_victory_chat(self):
        """Disegna la chat nella schermata vittoria."""
        chat_y = 380
        chat_x = 50
        chat_width = self.screen.get_width() - 100
        chat_height = 120

        # Box della chat
        pygame.draw.rect(self.screen, (40, 40, 40),
                         (chat_x, chat_y, chat_width, chat_height))
        pygame.draw.rect(self.screen, (100, 100, 100),
                         (chat_x, chat_y, chat_width, chat_height), 2)

        # Mostra messaggi chat
        if "chat_messages" in self.state:
            msg_y = chat_y + 5
            for msg in self.state["chat_messages"][-5:]:  # Mostra ultimi 5 messaggi
                if msg_y + 18 > chat_y + chat_height - 25:
                    break

                if msg["is_system"]:
                    msg_text = self.small_font.render(msg["message"], True, (150, 150, 150))
                elif msg.get("is_spectator", False):
                    msg_text = self.small_font.render(f"S{msg['player_id']}: {msg['message']}", True, (200, 200, 200))
                else:
                    pid = msg["player_id"]
                    color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                    msg_text = self.small_font.render(f"P{pid}: {msg['message']}", True, color)

                self.screen.blit(msg_text, (chat_x + 5, msg_y))
                msg_y += 18

        # Input chat
        input_y = chat_y + chat_height - 20
        if self.chat_active:
            pygame.draw.rect(self.screen, (60, 60, 60),
                             (chat_x, input_y, chat_width, 20))
            pygame.draw.rect(self.screen, (255, 255, 255),
                             (chat_x, input_y, chat_width, 20), 2)

            input_text = self.small_font.render(self.chat_input, True, (255, 255, 255))
            self.screen.blit(input_text, (chat_x + 5, input_y + 2))

            if self.cursor_visible:
                cursor_x = chat_x + 5 + input_text.get_width()
                pygame.draw.line(self.screen, (255, 255, 255),
                                 (cursor_x, input_y + 2),
                                 (cursor_x, input_y + 17), 1)
        else:
            chat_hint = self.small_font.render("Press T to chat", True, (150, 150, 150))
            self.screen.blit(chat_hint, (chat_x + 5, input_y + 2))

    def generate_session_id(self):
        """Genera un ID di sessione univoco basato su PID + timestamp + MAC address."""
        try:
            import psutil

            # PID del processo corrente
            pid = os.getpid()

            # Timestamp di avvio del processo (più preciso del tempo corrente)
            process = psutil.Process(pid)
            start_time = process.create_time()

            # MAC address della prima interfaccia di rete
            mac_address = None
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == psutil.AF_LINK and addr.address and addr.address != "00:00:00:00:00:00":
                        mac_address = addr.address
                        break
                if mac_address:
                    break

            # Se non troviamo il MAC, usa hostname + user
            if not mac_address:
                mac_address = f"{platform.node()}_{os.getlogin()}"

            # Combina tutti i dati
            session_data = f"{pid}_{start_time}_{mac_address}_{platform.system()}"

            # Genera hash SHA256 e prendi i primi 16 caratteri
            session_id = hashlib.sha256(session_data.encode()).hexdigest()[:16]

            print(f"[SESSION] Generated session ID: {session_id}")
            print(f"[SESSION] Based on: PID={pid}, START={start_time}, MAC={mac_address}")

            return session_id

        except ImportError:
            print("[SESSION] psutil not available, using fallback method")
            return self.generate_session_id_fallback()
        except Exception as e:
            print(f"[SESSION] Error generating session ID: {e}, using fallback")
            return self.generate_session_id_fallback()

    def generate_session_id_fallback(self):
        """Metodo fallback per generare session ID senza psutil."""
        try:
            # PID del processo
            pid = os.getpid()

            # Timestamp corrente con microsecondi
            timestamp = time.time()

            # Hostname del sistema
            hostname = platform.node()

            # Username (se disponibile)
            try:
                username = os.getlogin()
            except:
                username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))

            # Sistema operativo
            system = platform.system()

            # Combina tutti i dati
            session_data = f"{pid}_{timestamp}_{hostname}_{username}_{system}_{random.randint(1000, 9999)}"

            # Genera hash
            session_id = hashlib.sha256(session_data.encode()).hexdigest()[:16]

            print(f"[SESSION FALLBACK] Generated session ID: {session_id}")
            print(f"[SESSION FALLBACK] Based on: PID={pid}, HOST={hostname}, USER={username}")

            return session_id

        except Exception as e:
            print(f"[SESSION FALLBACK] Error: {e}, using UUID")
            return str(uuid.uuid4())[:16]



    def send_session_handshake(self):
        """Invia l'handshake di sessione al server."""
        handshake = json.dumps({
            "type": "session_handshake",
            "session_id": self.session_id,
            "timestamp": time.time(),
            "platform": platform.system()
        })
        try:
            self.sock.sendall((handshake + "\n").encode())
            print(f"[CLIENT] Sent session handshake: {self.session_id}")
        except Exception as e:
            print(f"[CLIENT] Error sending session handshake: {e}")
            raise

    def handle_game_input(self, event):
        """Gestisce l'input durante il gioco (lobby, partita, vittoria)."""
        # Gestione chat (sempre disponibile)
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
        # Tasto X per uscire temporaneamente (solo per giocatori in lobby)
        elif (event.key == pygame.K_x and
              self.current_screen == "lobby" and
              not self.is_spectator and
              not self.chat_active):
            self.send_command("LEAVE_TEMPORARILY")
            self.return_to_name_entry()
        # Altri comandi del gioco
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

    def attempt_join_lobby(self):
        """Tenta di entrare nella lobby con il nome specificato."""
        self.player_name = self.name_input.strip()
        try:
            self.send_join_request()
        except Exception as e:
            self.show_error("Errore di connessione")
            print(f"Error joining: {e}")

    def send_join_request(self):
        """Invia richiesta di join con nome al server."""
        join_request = json.dumps({
            "type": "join_request",
            "session_id": self.session_id,
            "player_name": self.player_name,
            "timestamp": time.time()
        })
        try:
            self.sock.sendall((join_request + "\n").encode())
            print(f"[CLIENT] Sent join request for: {self.player_name}")
        except Exception as e:
            print(f"[CLIENT] Error sending join request: {e}")
            raise

    def return_to_name_entry(self):
        """Torna alla schermata di inserimento nome."""
        self.current_screen = "name_entry"
        self.name_input = self.player_name or ""
        self.name_input_active = True
        self.join_error_message = ""
        self.state = None

    def show_error(self, message):
        """Mostra un messaggio di errore temporaneo."""
        self.join_error_message = message
        self.error_timer = 120  # 4 secondi a 30 FPS invece di 3

    def draw_name_entry(self):
        """Disegna la schermata di inserimento nome e spiegazione del gioco senza sovrapposizioni."""
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

    def attempt_join_lobby(self):
        """Tenta di entrare nella lobby con il nome specificato."""
        self.player_name = self.name_input.strip()
        if len(self.player_name) < 2:
            self.show_error("Nome troppo corto (minimo 2 caratteri)")
            return

        try:
            # Invia l'handshake di sessione prima della richiesta di join
            self.send_session_handshake()
            time.sleep(0.1)  # Breve pausa per assicurare l'ordine
            self.send_join_request()
            print(f"[CLIENT] Attempting to join with name: {self.player_name}")
        except Exception as e:
            self.show_error("Errore di connessione")
            print(f"Error joining: {e}")

    def handle_name_entry_input(self, event):
        """Gestisce l'input nella schermata di inserimento nome."""
        if self.name_input_active:
            if event.key == pygame.K_RETURN:
                # Prova a entrare con il nome inserito
                if len(self.name_input.strip()) >= 2:
                    self.attempt_join_lobby()
                else:
                    self.show_error("Nome troppo corto (minimo 2 caratteri)")
            elif event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif event.key == pygame.K_ESCAPE:
                # Chiudi il gioco
                pygame.quit()
                exit()
            else:
                # Aggiungi carattere al nome (max 20 caratteri)
                if event.unicode and len(self.name_input) < 20 and event.unicode.isprintable():
                    self.name_input += event.unicode

    def handle_game_input(self, event):
        """Gestisce l'input durante il gioco (lobby, partita, vittoria)."""
        # Gestione chat (sempre disponibile)
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
        # Tasto X per uscire temporaneamente (solo per giocatori in lobby)
        elif (event.key == pygame.K_x and
              self.current_screen == "lobby" and
              not self.is_spectator and
              not self.chat_active):
            self.send_command("LEAVE_TEMPORARILY")
            self.return_to_name_entry()
        # Altri comandi del gioco
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
        self.error_timer = 90  # 3 secondi a 30 FPS

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
            # Pulsante X per uscire (coordinate aggiornate)
            exit_button = pygame.Rect(330, 110, 25, 25)
            if exit_button.collidepoint(mouse_x, mouse_y):
                print("[CLICK] Exit button clicked")
                self.send_command("LEAVE_TEMPORARILY")
                self.return_to_name_entry()

        elif self.current_screen == "name_entry":
            # Pulsante JOIN LOBBY
            join_button = pygame.Rect(240, 320, 200, 45)
            if join_button.collidepoint(mouse_x, mouse_y) and len(self.name_input.strip()) >= 2:
                print("[CLICK] Join button clicked")
                self.attempt_join_lobby()

            # Click nell'area di input nome per attivarlo
            name_box = pygame.Rect(150, 240, 380, 50)
            if name_box.collidepoint(mouse_x, mouse_y):
                self.name_input_active = True
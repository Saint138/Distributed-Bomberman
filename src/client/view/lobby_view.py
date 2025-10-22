"""
View for game lobby with multi-line chat
"""
import pygame
import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .base_view import BaseView
from .text_utils import wrap_text
from common.constants import PLAYER_COLORS

class LobbyView(BaseView):
    """Lobby screen"""
    def __init__(self, screen: pygame.Surface):
        super().__init__(screen)
        self.cursor_visible = True
        self.cursor_timer = 0

    def render(self, game_state, chat_input: str = "", chat_active: bool = False) -> None:
        """Renders lobby"""
        self.draw_background_gradient()
        self.update_animation()
        self.cursor_timer += 1
        if self.cursor_timer >= 15:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        self._draw_header(game_state)
        self._draw_players_panel(game_state)
        self._draw_chat_panel(game_state, chat_input, chat_active)
        self._draw_actions_panel(game_state)
        self._draw_identity(game_state)
        pygame.display.flip()

    def _draw_header(self, game_state) -> None:
        """Draws header"""
        self.draw_text_centered("BOMBERMAN", self.big_font, self.colors['text_primary'], 40)
        subtitle = "SPECTATOR MODE" if game_state.is_spectator else "LOBBY"
        self.draw_text_centered(subtitle, self.font, self.colors['warning'], 70)

    def _draw_players_panel(self, game_state) -> None:
        """Draws players panel"""
        panel = pygame.Rect(30, 100, 330, 160)
        self.draw_gradient_rect(self.screen, self.colors['bg_medium'], self.colors['bg_light'], panel)
        pygame.draw.rect(self.screen, self.colors['border_light'], panel, 3, border_radius=10)
        pygame.draw.circle(self.screen, self.colors['success'], (55, 120), 8)
        title = self.font.render("Players", True, self.colors['text_primary'])
        self.screen.blit(title, (70, 110))
        y_offset = 140
        connected_count = 0
        current_host = game_state.get_current_host()
        for i in range(4):
            player_found = False
            for pid, pdata in game_state.get_players().items():
                if int(pid) == i:
                    if pdata.get("disconnected", False):
                        break
                    player_found = True
                    connected_count += 1
                    player_name = pdata.get("name", f"Player {pid}")
                    player_text = player_name
                    if int(pid) == game_state.player_id and not game_state.is_spectator:
                        player_text += " (You)"
                    if int(pid) == current_host:
                        player_text += " [HOST]"
                    self._draw_player_slot(i, player_text, current_host, y_offset)
                    break
            if not player_found:
                self._draw_empty_slot(y_offset)
            y_offset += 30

    def _draw_player_slot(self, pid: int, text: str, current_host: int, y: int) -> None:
        """Draws a player slot"""
        label = self.font.render(text, True, (255, 255, 255))
        slot_width = max(label.get_width() + 20, 200)
        slot_rect = pygame.Rect(50, y - 5, slot_width, 25)
        color = PLAYER_COLORS[pid]
        pygame.draw.rect(self.screen, color, slot_rect, border_radius=5)
        pygame.draw.rect(self.screen, self.colors['border_light'], slot_rect, 2, border_radius=5)
        text_rect = label.get_rect(center=slot_rect.center)
        self.screen.blit(label, text_rect)
        if int(pid) == current_host:
            crown_rect = pygame.Rect(slot_rect.right + 5, slot_rect.y + 2, 20, 20)
            pygame.draw.rect(self.screen, (255, 215, 0), crown_rect, border_radius=3)
            crown_text = self.small_font.render("H", True, (0, 0, 0))
            crown_text_rect = crown_text.get_rect(center=crown_rect.center)
            self.screen.blit(crown_text, crown_text_rect)

    def _draw_empty_slot(self, y: int) -> None:
        """Draws an empty slot"""
        slot_rect = pygame.Rect(50, y - 5, 200, 25)
        pygame.draw.rect(self.screen, (40, 40, 50), slot_rect, border_radius=5)
        pygame.draw.rect(self.screen, (60, 60, 70), slot_rect, 1, border_radius=5)
        label = self.small_font.render("Empty Slot", True, self.colors['text_disabled'])
        text_rect = label.get_rect(center=slot_rect.center)
        self.screen.blit(label, text_rect)

    def _draw_chat_panel(self, game_state, chat_input: str, chat_active: bool) -> None:
        """Draws chat panel"""
        panel = pygame.Rect(380, 100, 280, 260)
        self.draw_gradient_rect(self.screen, self.colors['bg_medium'], self.colors['bg_light'], panel)
        pygame.draw.rect(self.screen, self.colors['border_light'], panel, 3, border_radius=10)
        pygame.draw.circle(self.screen, self.colors['warning'], (405, 120), 8)
        title = self.font.render("Chat", True, self.colors['text_primary'])
        self.screen.blit(title, (420, 110))
        msg_area = pygame.Rect(390, 140, 260, 180)
        pygame.draw.rect(self.screen, (20, 20, 25), msg_area, border_radius=5)
        pygame.draw.rect(self.screen, self.colors['border'], msg_area, 1, border_radius=5)
        self._draw_chat_messages(game_state, 145)
        self._draw_chat_input(chat_input, chat_active, 325)

    def _draw_chat_messages(self, game_state, start_y: int) -> None:
        """Draws chat messages with multi-line support"""
        msg_y = start_y
        max_y = 315
        messages = game_state.get_chat_messages()
        visible_messages = []
        total_height = 0
        for msg in reversed(messages):
            if msg["is_system"]:
                icon, color = "!", self.colors['warning']
                text = msg["message"]
            elif msg.get("is_spectator", False):
                icon, color = "S", self.colors['info']
                sender_name = self._get_spectator_name(game_state, msg["player_id"])
                text = f"{sender_name}: {msg['message']}"
            else:
                icon = "*"
                pid = int(msg["player_id"])
                color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
                sender_name = self._get_player_name(game_state, pid)
                text = f"{sender_name}: {msg['message']}"
            lines = wrap_text(text, 24)
            msg_height = len(lines) * 18 + 2
            if total_height + msg_height > (max_y - start_y):
                break
            visible_messages.insert(0, (icon, color, lines))
            total_height += msg_height
        for icon, color, lines in visible_messages:
            if msg_y + 18 > max_y:
                break
            icon_surf = self.small_font.render(icon, True, color)
            self.screen.blit(icon_surf, (395, msg_y))
            first_line = self.small_font.render(lines[0], True, self.colors['text_secondary'])
            self.screen.blit(first_line, (415, msg_y))
            msg_y += 18
            for line in lines[1:]:
                if msg_y + 18 > max_y:
                    break
                line_surf = self.small_font.render(line, True, self.colors['text_secondary'])
                self.screen.blit(line_surf, (415, msg_y))
                msg_y += 18
            msg_y += 2

    def _draw_chat_input(self, chat_input: str, chat_active: bool, y: int) -> None:
        """Draws chat input"""
        input_rect = pygame.Rect(390, y, 260, 25)
        if chat_active:
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.colors['success'], input_rect, 2, border_radius=5)
            max_width = input_rect.width - 15
            display_text = chat_input
            test_surface = self.small_font.render(display_text, True, self.colors['text_primary'])
            if test_surface.get_width() > max_width:
                for i in range(len(chat_input), 0, -1):
                    test_text = "..." + chat_input[-i:]
                    test_surface = self.small_font.render(test_text, True, self.colors['text_primary'])
                    if test_surface.get_width() <= max_width:
                        display_text = test_text
                        break
            input_text = self.small_font.render(display_text, True, self.colors['text_primary'])
            self.screen.blit(input_text, (395, y + 3))
            if self.cursor_visible:
                cursor_x = 395 + input_text.get_width()
                if cursor_x < input_rect.right - 10:
                    pygame.draw.line(self.screen, self.colors['success'], (cursor_x, y + 3), (cursor_x, y + 20), 2)
        else:
            pygame.draw.rect(self.screen, (30, 30, 40), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.colors['border'], input_rect, 1, border_radius=5)
            hint = self.small_font.render("Press T to chat", True, self.colors['text_disabled'])
            self.screen.blit(hint, (395, y + 3))

    def _draw_actions_panel(self, game_state) -> None:
        """Draws actions panel"""
        panel = pygame.Rect(100, 375, 480, 35)
        self.draw_gradient_rect(self.screen, (30, 30, 40), (40, 40, 50), panel)
        pygame.draw.rect(self.screen, self.colors['border'], panel, 2, border_radius=20)
        connected_count = game_state.connected_players_count()
        if game_state.is_spectator:
            self._draw_spectator_actions(connected_count)
        elif connected_count < 2:
            self._draw_waiting_message()
        elif game_state.is_host():
            self._draw_host_actions()
        else:
            self._draw_non_host_actions()

    def _draw_spectator_actions(self, connected_count: int) -> None:
        """Actions for spectators"""
        if connected_count < 4:
            join_rect = pygame.Rect(240, 380, 160, 25)
            self.draw_gradient_rect(self.screen, (0, 150, 0), (0, 200, 0), join_rect)
            pygame.draw.rect(self.screen, (0, 255, 0), join_rect, 2, border_radius=12)
            join_text = self.font.render("Press J to Join", True, (255, 255, 255))
            text_rect = join_text.get_rect(center=join_rect.center)
            self.screen.blit(join_text, text_rect)
        else:
            self.draw_text_centered("All slots are full", self.font, self.colors['danger'], 392)

    def _draw_waiting_message(self) -> None:
        """Waiting for players message"""
        self.draw_text_centered("Waiting for players...", self.font, self.colors['text_secondary'], 392)

    def _draw_host_actions(self) -> None:
        """Actions for host"""
        start_rect = pygame.Rect(240, 380, 160, 25)
        pulse = abs(math.sin(self.animation_timer * 0.05)) * 20
        color1 = (0, 150 + pulse, 0)
        color2 = (0, 200 + pulse, 0)
        self.draw_gradient_rect(self.screen, color1, color2, start_rect)
        pygame.draw.rect(self.screen, (0, 255, 0), start_rect, 2, border_radius=12)
        start_text = self.font.render("Press ENTER", True, (255, 255, 255))
        text_rect = start_text.get_rect(center=start_rect.center)
        self.screen.blit(start_text, text_rect)

    def _draw_non_host_actions(self) -> None:
        """Actions for non-host"""
        self.draw_text_centered("Waiting for host...", self.font, self.colors['text_secondary'], 392)

    def _draw_identity(self, game_state) -> None:
        """Draws player identity"""
        identity_text = f"You are: {game_state.player_name}"
        if game_state.is_spectator:
            identity_text += " (Spectator)"
        identity_surf = self.small_font.render(identity_text, True, self.colors['text_disabled'])
        self.screen.blit(identity_surf, (10, self.screen.get_height() - 55))

    @staticmethod
    def _get_player_name(game_state, pid: int) -> str:
        """Gets player name"""
        players = game_state.get_players()
        if str(pid) in players:
            return players[str(pid)].get("name", f"Player {pid}")
        return f"Player {pid}"

    @staticmethod
    def _get_spectator_name(game_state, sid: int) -> str:
        """Gets spectator name"""
        spectators = game_state.get_spectators()
        for spec_id, spec_data in spectators.items():
            if int(spec_id) == int(sid):
                return spec_data.get("name", f"Spectator {sid}")
        return "Unknown"
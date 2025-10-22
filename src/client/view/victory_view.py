"""
View for victory screen with multi-line chat
"""
import pygame
import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .base_view import BaseView
from .text_utils import wrap_text
from common.constants import PLAYER_COLORS

class VictoryView(BaseView):
    """Victory screen"""
    def __init__(self, screen: pygame.Surface):
        super().__init__(screen)
        self.cursor_visible = True
        self.cursor_timer = 0

    def render(self, game_state, chat_input: str = "", chat_active: bool = False) -> None:
        """Renders victory screen"""
        self._draw_animated_background()
        self.update_animation()
        self.cursor_timer += 1
        if self.cursor_timer >= 15:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        self._draw_victory_box(game_state)
        self._draw_controls(game_state)
        self._draw_chat_section(game_state, chat_input, chat_active)
        pygame.display.flip()

    def _draw_animated_background(self) -> None:
        """Draws animated background"""
        self.draw_gradient_rect(self.screen, (10, 5, 20), (30, 15, 50), (0, 0, self.screen.get_width(), self.screen.get_height()))
        for i in range(20):
            x = (self.animation_timer * 2 + i * 37) % self.screen.get_width()
            y = (self.animation_timer + i * 23) % self.screen.get_height()
            size = 2 + (i % 3)
            alpha = int(abs(math.sin((self.animation_timer + i * 10) * 0.02)) * 100 + 50)
            color = (alpha, alpha // 2, alpha)
            pygame.draw.circle(self.screen, color, (int(x), int(y)), size)

    def _draw_victory_box(self, game_state) -> None:
        """Draws main victory box"""
        main_box = pygame.Rect(120, 30, 440, 180)
        shadow_box = main_box.copy()
        shadow_box.x += 5
        shadow_box.y += 5
        self.draw_rounded_rect(self.screen, (5, 5, 15), shadow_box, radius=15)
        self.draw_gradient_rect(self.screen, (60, 60, 80), (40, 40, 60), main_box)
        border_pulse = abs(math.sin(self.animation_timer * 0.03)) * 30 + 180
        border_color = (int(border_pulse), int(border_pulse), 200)
        pygame.draw.rect(self.screen, border_color, main_box, 3, border_radius=15)
        winner_id = game_state.get_winner_id()
        victory_text, victory_color, sub_text = self._get_victory_text(game_state, winner_id)
        main_text = self.title_font.render(victory_text, True, (255, 255, 255))
        main_rect = main_text.get_rect(center=(340, 100))
        self.screen.blit(main_text, main_rect)
        if sub_text:
            sub_surf = self.font.render(sub_text, True, victory_color)
            sub_rect = sub_surf.get_rect(center=(340, 135))
            self.screen.blit(sub_surf, sub_rect)
        self._draw_victory_timer(game_state)

    def _get_victory_text(self, game_state, winner_id: int) -> tuple:
        """Determines victory text"""
        if winner_id == -1:
            return "DRAW!", self.colors['warning'], "No survivors"
        elif winner_id >= 0:
            players = game_state.get_players()
            winner_name = f"Player {winner_id}"
            if str(winner_id) in players:
                winner_name = players[str(winner_id)].get("name", f"Player {winner_id}")
            if len(winner_name) > 12:
                winner_name = winner_name[:12] + "..."
            victory_color = PLAYER_COLORS[winner_id % len(PLAYER_COLORS)]
            return winner_name.upper(), victory_color, "WINS!"
        else:
            return "GAME OVER", self.colors['danger'], ""

    def _draw_victory_timer(self, game_state) -> None:
        """Draws return to lobby timer"""
        timer = game_state.get_victory_timer()
        if timer > 0:
            timer_seconds = timer // 10 + 1
            timer_text = f"Lobby in {timer_seconds}s"
            timer_color = self.colors['text_secondary']
            if timer_seconds <= 3:
                pulse = abs(math.sin(self.animation_timer * 0.1)) * 50
                timer_color = (200 + int(pulse), 200 + int(pulse), 100)
            timer_surf = self.small_font.render(timer_text, True, timer_color)
            timer_rect = timer_surf.get_rect(center=(340, 165))
            self.screen.blit(timer_surf, timer_rect)

    def _draw_controls(self, game_state) -> None:
        """Draws controls"""
        control_y = 225
        if not game_state.is_spectator:
            button_rect = pygame.Rect(250, control_y, 180, 30)
            button_pulse = abs(math.sin(self.animation_timer * 0.05)) * 15
            button_color1 = (50 + button_pulse, 150 + button_pulse, 50)
            button_color2 = (30 + button_pulse, 100 + button_pulse, 30)
            self.draw_gradient_rect(self.screen, button_color1, button_color2, button_rect)
            pygame.draw.rect(self.screen, (100, 255, 100), button_rect, 2, border_radius=15)
            button_text = self.font.render("ENTER: Play Again", True, (255, 255, 255))
            button_text_rect = button_text.get_rect(center=button_rect.center)
            self.screen.blit(button_text, button_text_rect)
        else:
            spec_text = self.font.render("Waiting for next game...", True, self.colors['text_secondary'])
            spec_rect = spec_text.get_rect(center=(340, control_y + 15))
            self.screen.blit(spec_text, spec_rect)

    def _draw_chat_section(self, game_state, chat_input: str, chat_active: bool) -> None:
        """Draws chat section"""
        chat_y = 270
        chat_height = self.screen.get_height() - chat_y - 10
        chat_box = pygame.Rect(30, chat_y, self.screen.get_width() - 60, chat_height)
        self.draw_rounded_rect(self.screen, self.colors['bg_medium'], chat_box, radius=10)
        pygame.draw.rect(self.screen, self.colors['border'], chat_box, 2, border_radius=10)
        title = self.font.render("Chat", True, self.colors['text_primary'])
        self.screen.blit(title, (45, chat_y + 8))
        self._draw_chat_messages(game_state, chat_y, chat_height)
        self._draw_chat_input(chat_y, chat_height, chat_input, chat_active)

    def _draw_chat_messages(self, game_state, chat_y: int, chat_height: int) -> None:
        """Draws chat messages with multi-line support"""
        msg_start_y = chat_y + 35
        msg_area_height = chat_height - 70
        max_y = chat_y + chat_height - 35
        messages = game_state.get_chat_messages()
        visible_messages = []
        total_height = 0
        for msg in reversed(messages):
            color, text = self._format_message(game_state, msg)
            lines = wrap_text(text, 65)
            msg_height = len(lines) * 18 + 3
            if total_height + msg_height > msg_area_height:
                break
            visible_messages.insert(0, (color, lines))
            total_height += msg_height
        msg_y = msg_start_y
        for color, lines in visible_messages:
            for line in lines:
                if msg_y + 18 > max_y:
                    break
                msg_surf = self.small_font.render(line, True, color)
                self.screen.blit(msg_surf, (45, msg_y))
                msg_y += 18
            msg_y += 3

    def _format_message(self, game_state, msg: dict) -> tuple:
        """Formats a chat message"""
        if msg["is_system"]:
            return self.colors['warning'], f"[SYSTEM] {msg['message']}"
        elif msg.get("is_spectator", False):
            sender_name = self._get_spectator_name(game_state, msg["player_id"])
            return self.colors['info'], f"[SPEC] {sender_name}: {msg['message']}"
        else:
            pid = int(msg["player_id"])
            color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
            sender_name = self._get_player_name(game_state, pid)
            return color, f"{sender_name}: {msg['message']}"

    def _draw_chat_input(self, chat_y: int, chat_height: int, chat_input: str, chat_active: bool) -> None:
        """Draws chat input"""
        input_y = chat_y + chat_height - 30
        input_rect = pygame.Rect(40, input_y, self.screen.get_width() - 80, 25)
        if chat_active:
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=8)
            pygame.draw.rect(self.screen, self.colors['success'], input_rect, 2, border_radius=8)
            display_text = chat_input
            if len(display_text) > 60:
                display_text = "..." + display_text[-57:]
            input_text = self.small_font.render(display_text, True, self.colors['text_primary'])
            self.screen.blit(input_text, (45, input_y + 3))
            if self.cursor_visible:
                cursor_x = 45 + input_text.get_width()
                if cursor_x < input_rect.right - 10:
                    pygame.draw.line(self.screen, self.colors['success'], (cursor_x, input_y + 3), (cursor_x, input_y + 20), 2)
        else:
            pygame.draw.rect(self.screen, self.colors['bg_light'], input_rect, border_radius=8)
            pygame.draw.rect(self.screen, self.colors['border'], input_rect, 1, border_radius=8)
            hint = self.small_font.render("Press T to chat", True, self.colors['text_disabled'])
            self.screen.blit(hint, (45, input_y + 3))

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
        for spec_id, spec_data in game_state.get_spectators().items():
            if int(spec_id) == int(sid):
                return spec_data.get("name", f"Spectator {sid}")
        return "Unknown"
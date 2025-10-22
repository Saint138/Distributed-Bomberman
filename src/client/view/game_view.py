"""
View for gameplay with multi-line chat
"""
import pygame
import math
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .base_view import BaseView
from .text_utils import wrap_text
from common.constants import (TILE_SIZE, TILE_EMPTY, TILE_WALL, TILE_BLOCK, PLAYER_COLORS, MAP_WIDTH, MAP_HEIGHT)

class GameView(BaseView):
    """Game screen"""
    def __init__(self, screen: pygame.Surface, sidebar_width: int = 200):
        super().__init__(screen)
        self.map_width_px = MAP_WIDTH * TILE_SIZE
        self.map_height_px = MAP_HEIGHT * TILE_SIZE
        self.sidebar_width = sidebar_width
        self.cursor_visible = True
        self.cursor_timer = 0

    def render(self, game_state, chat_input: str = "", chat_active: bool = False) -> None:
        """Renders ongoing game"""
        self.screen.fill(self.colors['bg_dark'])
        self.update_animation()
        self.cursor_timer += 1
        if self.cursor_timer >= 15:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
        self._draw_game_area(game_state)
        self._draw_sidebar(game_state, chat_input, chat_active)
        pygame.display.flip()

    def _draw_game_area(self, game_state) -> None:
        """Draws game area"""
        shadow_rect = pygame.Rect(5, 5, self.map_width_px, self.map_height_px)
        pygame.draw.rect(self.screen, (5, 5, 10), shadow_rect)
        pygame.draw.rect(self.screen, (20, 20, 25), (0, 0, self.map_width_px, self.map_height_px))
        self._draw_map(game_state.get_map())
        self._draw_bombs(game_state.get_bombs())
        self._draw_explosions(game_state.get_explosions())
        self._draw_players(game_state)
        if game_state.is_spectator:
            self._draw_spectator_indicator()

    def _draw_map(self, game_map: list) -> None:
        """Draws the map"""
        for y, row in enumerate(game_map):
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
                    pygame.draw.line(self.screen, (130, 65, 0), (rect.x + 5, rect.y + 5), (rect.x + 15, rect.y + 15), 2)

    def _draw_bombs(self, bombs: list) -> None:
        """Draws bombs"""
        for bomb in bombs:
            if bomb.get("timer", 0) > 0:
                bomb_x = bomb["x"] * TILE_SIZE + TILE_SIZE // 2
                bomb_y = bomb["y"] * TILE_SIZE + TILE_SIZE // 2
                pulse = abs(math.sin(self.animation_timer * 0.1)) * 3
                radius = 12 + pulse
                pygame.draw.circle(self.screen, (20, 0, 0), (bomb_x + 2, bomb_y + 2), radius)
                pygame.draw.circle(self.screen, (60, 0, 0), (bomb_x, bomb_y), radius)
                pygame.draw.circle(self.screen, (255, 0, 0), (bomb_x, bomb_y), radius, 3)
                pygame.draw.circle(self.screen, (255, 100, 100), (bomb_x - 4, bomb_y - 4), 4)

    def _draw_explosions(self, explosions: list) -> None:
        """Draws explosions"""
        for explosion in explosions:
            for ex, ey in explosion["positions"]:
                rect = pygame.Rect(ex * TILE_SIZE, ey * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                for i in range(3):
                    flame_rect = rect.inflate(-i*8, -i*8)
                    color = (255, 200 - i*50, 0)
                    pygame.draw.rect(self.screen, color, flame_rect)

    def _draw_players(self, game_state) -> None:
        """Draws players"""
        for pid, pdata in game_state.get_players().items():
            if pdata["alive"] and not pdata.get("disconnected", False):
                player_x = pdata["x"] * TILE_SIZE
                player_y = pdata["y"] * TILE_SIZE
                shadow_rect = pygame.Rect(player_x + 3, player_y + 3, TILE_SIZE - 2, TILE_SIZE - 2)
                pygame.draw.ellipse(self.screen, (10, 10, 15), shadow_rect)
                color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                player_rect = pygame.Rect(player_x + 2, player_y + 2, TILE_SIZE - 4, TILE_SIZE - 4)
                pygame.draw.rect(self.screen, color, player_rect, border_radius=8)
                pygame.draw.rect(self.screen, (255, 255, 255), player_rect, 2, border_radius=8)
                num_text = self.small_font.render(str(pid), True, (0, 0, 0))
                num_rect = num_text.get_rect(center=player_rect.center)
                self.screen.blit(num_text, num_rect)

    def _draw_spectator_indicator(self) -> None:
        """Draws spectator indicator"""
        spec_surf = pygame.Surface((200, 30))
        spec_surf.set_alpha(200)
        spec_surf.fill((0, 0, 0))
        self.screen.blit(spec_surf, (10, 10))
        spec_text = self.font.render("SPECTATOR MODE", True, self.colors['warning'])
        self.screen.blit(spec_text, (20, 15))

    def _draw_sidebar(self, game_state, chat_input: str, chat_active: bool) -> None:
        """Draws sidebar"""
        sidebar_x = self.map_width_px
        sidebar_rect = pygame.Rect(sidebar_x, 0, self.sidebar_width, self.map_height_px)
        self.draw_gradient_rect(self.screen, self.colors['bg_medium'], self.colors['bg_dark'], sidebar_rect)
        pygame.draw.line(self.screen, self.colors['border'], (sidebar_x, 0), (sidebar_x, self.map_height_px), 3)
        self._draw_players_panel(game_state, sidebar_x, 10)
        self._draw_spectators_counter(game_state, sidebar_x, 180)
        self._draw_chat_panel(game_state, sidebar_x, 220, chat_input, chat_active)

    def _draw_players_panel(self, game_state, x: int, y: int) -> None:
        """Draws players panel"""
        panel = pygame.Rect(x + 10, y, self.sidebar_width - 20, 160)
        self.draw_rounded_rect(self.screen, self.colors['bg_light'], panel)
        pygame.draw.rect(self.screen, self.colors['border'], panel, 2, border_radius=8)
        title = self.font.render("Players", True, self.colors['text_primary'])
        self.screen.blit(title, (x + 20, y + 5))
        slot_y = y + 30
        for slot_id in range(4):
            if slot_y > y + 150:
                break
            self._draw_player_slot(game_state, slot_id, x, slot_y)
            slot_y += 28

    def _draw_player_slot(self, game_state, slot_id: int, x: int, y: int) -> None:
        """Draws a player slot in sidebar"""
        player_name = f"Slot {slot_id}"
        status_color = self.colors['text_disabled']
        status_text = "empty slot"
        for pid, pdata in game_state.get_players().items():
            if int(pid) == slot_id:
                player_name = pdata.get("name", f"Player {pid}")
                if int(pid) == game_state.player_id and not game_state.is_spectator:
                    player_name += " (YOU)"
                if pdata.get("disconnected", False):
                    status_color = self.colors['text_disabled']
                    status_text = "disconnected"
                elif not pdata["alive"] or pdata.get("lives", 0) <= 0:
                    status_color = self.colors['danger']
                    status_text = "eliminated"
                else:
                    status_color = PLAYER_COLORS[int(pid) % len(PLAYER_COLORS)]
                    status_text = "♥" * pdata.get("lives", 0)
                break
        pygame.draw.circle(self.screen, status_color, (x + 25, y + 8), 6)
        player_text = player_name[:15] + "..." if len(player_name) > 15 else player_name
        player_surf = self.small_font.render(player_text, True, self.colors['text_primary'])
        self.screen.blit(player_surf, (x + 35, y))
        status_surf = self.small_font.render(status_text, True, status_color)
        self.screen.blit(status_surf, (x + 35, y + 12))

    def _draw_spectators_counter(self, game_state, x: int, y: int) -> None:
        """Draws spectators counter"""
        spectators = game_state.get_spectators()
        if spectators:
            spec_count = len(spectators)
            spec_rect = pygame.Rect(x + 10, y, self.sidebar_width - 20, 25)
            pygame.draw.rect(self.screen, self.colors['bg_light'], spec_rect, border_radius=5)
            text = self.small_font.render(f"👁 {spec_count} Spectators", True, self.colors['info'])
            self.screen.blit(text, (x + 20, y + 5))

    def _draw_chat_panel(self, game_state, x: int, y: int, chat_input: str, chat_active: bool) -> None:
        """Draws chat panel"""
        panel_height = self.map_height_px - y - 10
        panel = pygame.Rect(x + 10, y, self.sidebar_width - 20, panel_height)
        self.draw_rounded_rect(self.screen, self.colors['bg_light'], panel)
        pygame.draw.rect(self.screen, self.colors['border'], panel, 2, border_radius=8)
        header = pygame.Rect(x + 10, y, self.sidebar_width - 20, 25)
        self.draw_gradient_rect(self.screen, self.colors['bg_medium'], self.colors['bg_light'], header)
        title = self.small_font.render("💬 Chat", True, self.colors['text_primary'])
        self.screen.blit(title, (x + 20, y + 5))
        msg_y = y + 30
        msg_area_height = self.map_height_px - y - 65
        messages = game_state.get_chat_messages()
        visible_messages = []
        total_height = 0
        for msg in reversed(messages):
            color, text = self._format_chat_message(game_state, msg)
            lines = wrap_text(text, 18)
            msg_height = len(lines) * 16 + 4
            if total_height + msg_height > msg_area_height:
                break
            visible_messages.insert(0, (color, lines))
            total_height += msg_height
        for color, lines in visible_messages:
            for line in lines:
                if msg_y > self.map_height_px - 50:
                    break
                msg_surf = self.small_font.render(line, True, color)
                self.screen.blit(msg_surf, (x + 15, msg_y))
                msg_y += 16
            msg_y += 4
        self._draw_chat_input_in_sidebar(x, chat_input, chat_active)

    def _format_chat_message(self, game_state, msg: dict) -> tuple:
        """Formats a chat message"""
        if msg["is_system"]:
            return self.colors['warning'], msg["message"]
        elif msg.get("is_spectator", False):
            sender_name = self._get_spectator_name(game_state, msg["player_id"])
            return self.colors['info'], f"{sender_name}: {msg['message']}"
        else:
            pid = int(msg["player_id"])
            color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
            sender_name = self._get_player_name(game_state, pid)
            return color, f"{sender_name}: {msg['message']}"

    def _draw_chat_input_in_sidebar(self, x: int, chat_input: str, chat_active: bool) -> None:
        """Draws chat input in sidebar"""
        input_y = self.map_height_px - 35
        input_rect = pygame.Rect(x + 15, input_y, self.sidebar_width - 30, 20)
        if chat_active:
            pygame.draw.rect(self.screen, (40, 40, 50), input_rect, border_radius=5)
            pygame.draw.rect(self.screen, self.colors['success'], input_rect, 2, border_radius=5)
            display_text = chat_input[-15:] if len(chat_input) > 15 else chat_input
            input_text = self.small_font.render(display_text, True, self.colors['text_primary'])
            self.screen.blit(input_text, (x + 18, input_y + 2))
            if self.cursor_visible:
                cursor_x = x + 18 + input_text.get_width()
                pygame.draw.line(self.screen, self.colors['success'], (cursor_x, input_y + 2), (cursor_x, input_y + 17), 2)
        else:
            pygame.draw.rect(self.screen, self.colors['bg_medium'], input_rect, border_radius=5)
            hint = self.small_font.render("T: Chat", True, self.colors['text_disabled'])
            self.screen.blit(hint, (x + 18, input_y + 2))

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
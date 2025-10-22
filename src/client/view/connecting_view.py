"""
View for connection screen
"""
import pygame
import math
from .base_view import BaseView

class ConnectingView(BaseView):
    """Screen shown during server connection"""
    def __init__(self, screen: pygame.Surface):
        super().__init__(screen)
        self.connection_timer = 0

    def render(self, game_state, **kwargs) -> None:
        """Renders the connection screen"""
        self.draw_background_gradient()
        self.update_animation()
        self.connection_timer += 1
        self.draw_text_centered("BOMBERMAN", self.big_font, self.colors['text_primary'], 150)
        dots = "." * ((self.connection_timer // 30) % 4)
        self.draw_text_centered(f"Connecting to server{dots}", self.font, self.colors['warning'], 220)
        self._draw_spinner(self.screen.get_width() // 2, 280)
        self.draw_text_centered("Press ESC to exit", self.small_font, self.colors['text_disabled'], 350)
        pygame.display.flip()

    def _draw_spinner(self, center_x: int, center_y: int) -> None:
        """Draws a rotating spinner"""
        radius = 20
        angle = (self.connection_timer * 5) % 360
        for i in range(8):
            current_angle = angle + i * 45
            end_x = center_x + math.cos(math.radians(current_angle)) * radius
            end_y = center_y + math.sin(math.radians(current_angle)) * radius
            alpha = 255 - (i * 30)
            color = (alpha, alpha, alpha)
            pygame.draw.circle(self.screen, color, (int(end_x), int(end_y)), 3)
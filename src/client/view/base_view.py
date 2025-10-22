"""
Base view with common rendering utilities
"""
import pygame
import sys
import os
from typing import Union
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.constants import UI_COLORS

class BaseView:
    """Base class for all views with common rendering methods"""
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.colors = UI_COLORS
        self.font = pygame.font.SysFont("Arial", 20)
        self.small_font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 36, bold=True)
        self.big_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.animation_timer = 0

    def update_animation(self) -> None:
        """Updates animation timer"""
        self.animation_timer += 1

    @staticmethod
    def draw_gradient_rect(surface: pygame.Surface, color1: tuple, color2: tuple, rect: Union[tuple, pygame.Rect], vertical: bool = True) -> None:
        """Draws a rectangle with gradient"""
        if isinstance(rect, pygame.Rect):
            x, y, w, h = rect.x, rect.y, rect.width, rect.height
        else:
            x, y, w, h = rect
        length = h if vertical else w
        for i in range(length):
            ratio = i / length
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            if vertical:
                pygame.draw.line(surface, (r, g, b), (x, y + i), (x + w, y + i))
            else:
                pygame.draw.line(surface, (r, g, b), (x + i, y), (x + i, y + h))

    @staticmethod
    def draw_rounded_rect(surface: pygame.Surface, color: tuple, rect: Union[tuple, pygame.Rect], radius: int = 10) -> None:
        """Draws a rounded rectangle"""
        if isinstance(rect, pygame.Rect):
            x, y, w, h = rect.x, rect.y, rect.width, rect.height
        else:
            x, y, w, h = rect
        pygame.draw.rect(surface, color, (x + radius, y, w - 2 * radius, h))
        pygame.draw.rect(surface, color, (x, y + radius, w, h - 2 * radius))
        pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + radius, y + h - radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + h - radius), radius)

    def draw_text_centered(self, text: str, font: pygame.font.Font, color: tuple, y: int) -> None:
        """Draws horizontally centered text"""
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self.screen.get_width() // 2, y))
        self.screen.blit(surface, rect)

    def draw_background_gradient(self) -> None:
        """Draws a gradient background"""
        self.draw_gradient_rect(self.screen, (20, 20, 30), (40, 40, 60), (0, 0, self.screen.get_width(), self.screen.get_height()))

    def render(self, game_state, **kwargs) -> None:
        """Method to be implemented in subclasses"""
        raise NotImplementedError("Subclasses must implement render()")
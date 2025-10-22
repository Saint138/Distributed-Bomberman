"""
Text handling utilities for views
"""
import pygame
from typing import List, Tuple

def wrap_text(text: str, max_chars: int) -> List[str]:
    """
    Splits text into lines that don't exceed max_chars characters,
    trying to break on spaces when possible.

    Args:
        text: The text to split
        max_chars: Maximum characters per line

    Returns:
        List of strings, one per line
    """
    if len(text) <= max_chars:
        return [text]
    lines = []
    current_line = ""
    words = text.split(" ")
    for word in words:
        if len(word) > max_chars:
            if current_line:
                lines.append(current_line.strip())
                current_line = ""
            for i in range(0, len(word), max_chars):
                lines.append(word[i:i+max_chars])
            continue
        test_line = current_line + " " + word if current_line else word
        if len(test_line) <= max_chars:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())
    return lines

def render_multiline_text(surface: pygame.Surface, font: pygame.font.Font, text: str, color: tuple, start_pos: Tuple[int, int], max_chars: int, line_spacing: int = 2) -> int:
    """
    Renders multi-line text with automatic word wrap.

    Args:
        surface: Pygame surface to draw on
        font: Font to use
        text: Text to render
        color: Text color (R, G, B)
        start_pos: Starting position (x, y)
        max_chars: Maximum characters per line
        line_spacing: Extra spacing between lines

    Returns:
        Total height occupied by text (in pixels)
    """
    lines = wrap_text(text, max_chars)
    x, y = start_pos
    total_height = 0
    for line in lines:
        text_surface = font.render(line, True, color)
        surface.blit(text_surface, (x, y))
        line_height = text_surface.get_height()
        y += line_height + line_spacing
        total_height += line_height + line_spacing
    return total_height

def truncate_text(text: str, max_chars: int, suffix: str = "...") -> str:
    """
    Truncates text if it exceeds max_chars, adding a suffix.

    Args:
        text: Text to truncate
        max_chars: Maximum length (including suffix)
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix
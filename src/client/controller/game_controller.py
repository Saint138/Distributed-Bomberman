"""
Controller to handle user input
"""
import pygame
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.constants import MAX_MESSAGE_LENGTH

class GameController:
    """Handles user input and translates it into commands"""
    def __init__(self, network_manager):
        self.network = network_manager
        self.chat_input = ""
        self.chat_active = False

    def handle_event(self, event: pygame.event.Event, game_state) -> bool:
        """
        Handles a pygame event

        Returns:
            True if the game should continue, False to exit
        """
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self._handle_keydown(event, game_state)
        return True

    def _handle_keydown(self, event: pygame.event.Event, game_state) -> bool:
        """Handles key press events"""
        screen = game_state.current_screen
        if screen == "connecting":
            if event.key == pygame.K_ESCAPE:
                return False
        elif event.key == pygame.K_t and not self.chat_active:
            self._activate_chat()
        elif self.chat_active:
            return self._handle_chat_input(event)
        elif screen == "lobby":
            self._handle_lobby_input(event, game_state)
        elif screen == "game":
            self._handle_game_input(event, game_state)
        elif screen == "victory":
            self._handle_victory_input(event, game_state)
        return True

    def _activate_chat(self) -> None:
        """Activates chat mode"""
        self.chat_active = True
        self.chat_input = ""

    def _handle_chat_input(self, event: pygame.event.Event) -> bool:
        """Handles input when chat is active"""
        if event.key == pygame.K_RETURN:
            if self.chat_input.strip():
                self.network.send_command(f"CHAT:{self.chat_input}")
            self.chat_input = ""
            self.chat_active = False
        elif event.key == pygame.K_ESCAPE:
            self.chat_input = ""
            self.chat_active = False
        elif event.key == pygame.K_BACKSPACE:
            self.chat_input = self.chat_input[:-1]
        else:
            if event.unicode and len(self.chat_input) < MAX_MESSAGE_LENGTH:
                self.chat_input += event.unicode
        return True

    def _handle_lobby_input(self, event: pygame.event.Event, game_state) -> None:
        """Handles input in lobby"""
        if game_state.is_spectator:
            if event.key == pygame.K_j:
                if game_state.connected_players_count() < 4:
                    self.network.send_command("JOIN_GAME")
        else:
            if event.key == pygame.K_RETURN and game_state.is_host():
                if game_state.can_start_game():
                    self.network.send_command("START_GAME")

    def _handle_game_input(self, event: pygame.event.Event, game_state) -> None:
        """Handles input during gameplay"""
        if game_state.is_spectator:
            return
        if game_state.get_game_state() != "playing":
            return
        if event.key == pygame.K_UP:
            self.network.send_command("UP")
        elif event.key == pygame.K_DOWN:
            self.network.send_command("DOWN")
        elif event.key == pygame.K_LEFT:
            self.network.send_command("LEFT")
        elif event.key == pygame.K_RIGHT:
            self.network.send_command("RIGHT")
        elif event.key == pygame.K_SPACE:
            self.network.send_command("BOMB")

    def _handle_victory_input(self, event: pygame.event.Event, game_state) -> None:
        """Handles input in victory screen"""
        if not game_state.is_spectator and event.key == pygame.K_RETURN:
            self.network.send_command("PLAY_AGAIN")

    def get_chat_input(self) -> str:
        """Returns current chat text"""
        return self.chat_input

    def is_chat_active(self) -> bool:
        """Checks if chat is active"""
        return self.chat_active
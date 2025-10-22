"""
Main client game orchestrator
"""
import pygame
import socket
import sys
import os

current_file = os.path.abspath(__file__)
client_dir = os.path.dirname(current_file)
src_dir = os.path.dirname(client_dir)

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from client.model.game_state import GameState
from client.view.connecting_view import ConnectingView
from client.view.lobby_view import LobbyView
from client.view.game_view import GameView
from client.view.victory_view import VictoryView
from client.controller.game_controller import GameController
from client.network.client_network import NetworkManager
from common.constants import TILE_SIZE, MAP_WIDTH, MAP_HEIGHT

class BombermanClient:
    """Main client class - Orchestrates Model, View, Controller"""
    def __init__(self, sock: socket.socket):
        pygame.init()
        self.map_width_px = MAP_WIDTH * TILE_SIZE
        self.map_height_px = MAP_HEIGHT * TILE_SIZE
        self.sidebar_width = 200
        self.screen = pygame.display.set_mode((self.map_width_px + self.sidebar_width, self.map_height_px))
        pygame.display.set_caption("Bomberman")
        self.clock = pygame.time.Clock()
        self.model = GameState()
        self.network = NetworkManager(sock)
        self.controller = GameController(self.network)
        self.views = {
            "connecting": ConnectingView(self.screen),
            "lobby": LobbyView(self.screen),
            "game": GameView(self.screen, self.sidebar_width),
            "victory": VictoryView(self.screen)
        }
        self._setup_network_callbacks()
        self.network.start_receiving()

    def _setup_network_callbacks(self) -> None:
        """Sets up network manager callbacks"""
        self.network.on_state_update = self._on_state_received
        self.network.on_join_success = self._on_join_success
        self.network.on_conversion = self._on_conversion

    def _on_state_received(self, state: dict) -> None:
        """Callback when new state is received"""
        self.model.update(state)

    def _on_join_success(self, player_id: int, is_spectator: bool, name: str) -> None:
        """Callback when join is successful"""
        self.model.set_player_info(player_id, is_spectator, name)
        print(f"[CLIENT] Successfully joined as {name}")

    def _on_conversion(self, new_player_id: int, is_spectator: bool) -> None:
        """Callback when spectator is converted to player"""
        self.model.player_id = new_player_id
        self.model.is_spectator = is_spectator
        print(f"[CLIENT] Converted to Player {new_player_id}")

    def run(self) -> None:
        """Main game loop"""
        running = True
        while running:
            self.clock.tick(30)
            for event in pygame.event.get():
                if not self.controller.handle_event(event, self.model):
                    running = False
                    break
            self._render_current_view()
        self.network.stop()
        pygame.quit()

    def _render_current_view(self) -> None:
        """Renders current view based on state"""
        screen = self.model.current_screen
        view = self.views.get(screen)
        if view:
            if screen in ["lobby", "game", "victory"]:
                view.render(self.model, chat_input=self.controller.get_chat_input(), chat_active=self.controller.is_chat_active())
            else:
                view.render(self.model)
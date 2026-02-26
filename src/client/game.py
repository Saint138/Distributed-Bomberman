"""
Main client game orchestrator - with proxy reconnection support.

When the proxy crashes and comes back, the client automatically reconnects
without destroying the pygame window. A "Reconnecting..." overlay is shown
during the reconnection window.
"""
import pygame
import socket
import sys
import os
import time

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

# Sentinel raised by NetworkManager callbacks when connection is lost
class ConnectionLost(Exception):
    pass


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
            "lobby":      LobbyView(self.screen),
            "game":       GameView(self.screen, self.sidebar_width),
            "victory":    VictoryView(self.screen),
        }
        self._connection_lost = False
        self._setup_network_callbacks()
        self.network.start_receiving()

    # ------------------------------------------------------------------
    # Network callbacks
    # ------------------------------------------------------------------

    def _setup_network_callbacks(self) -> None:
        self.network.on_state_update  = self._on_state_received
        self.network.on_join_success  = self._on_join_success
        self.network.on_conversion    = self._on_conversion
        self.network.on_disconnected  = self._on_disconnected   # NEW

    def _on_state_received(self, state: dict) -> None:
        self.model.update(state)

    def _on_join_success(self, player_id: int, is_spectator: bool, name: str, reconnected: bool = False) -> None:
        if reconnected:
            # Just update identity, don't reset current_screen to lobby
            # The next state broadcast will restore the correct game state
            self.model.player_id = player_id
            self.model.is_spectator = is_spectator
            print(f"[CLIENT] Session restored as {name} (player_id={player_id})")
        else:
            self.model.set_player_info(player_id, is_spectator, name)
            print(f"[CLIENT] Successfully joined as {name}")
        self._connection_lost = False

    def _on_conversion(self, new_player_id: int, is_spectator: bool) -> None:
        self.model.player_id = new_player_id
        self.model.is_spectator = is_spectator
        print(f"[CLIENT] Converted to Player {new_player_id}")

    def _on_disconnected(self) -> None:
        """Called by NetworkManager when the socket closes unexpectedly."""
        if not self._connection_lost:
            self._connection_lost = True
            print("[CLIENT] Connection lost -- waiting for proxy to come back...")

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    def reconnect(self, new_sock: socket.socket) -> None:
        """
        Replace the underlying socket/NetworkManager with a fresh connection.
        pygame and the game window are kept alive -- no flicker.
        If we have a session_id, sends RECONNECT so the primary restores
        the existing session instead of treating this as a new join.
        """
        print("[CLIENT] Reconnecting with new socket...")
        old_session_id = self.network.session_id   # preserve across reconnect
        try:
            self.network.stop()
        except Exception:
            pass

        self.network = NetworkManager(new_sock)
        self.network.session_id = old_session_id   # carry over
        self.controller = GameController(self.network)
        self._connection_lost = False
        self._setup_network_callbacks()

        # Send RECONNECT *before* starting the receive loop so the
        # primary handles it as the very first message on this connection.
        if old_session_id:
            self.network.send_reconnect()

        self.network.start_receiving()
        print("[CLIENT] Reconnected OK")

    @property
    def is_disconnected(self) -> bool:
        return self._connection_lost

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main game loop.

        Returns normally when the user closes the window.
        Sets self._connection_lost = True and returns when the network
        connection drops -- the caller (mainClient.py) is expected to
        reconnect and call run() again, or call reconnect(new_sock)
        before calling run() again.
        """
        running = True
        while running:
            self.clock.tick(30)

            for event in pygame.event.get():
                if not self.controller.handle_event(event, self.model):
                    running = False
                    break

            # If the connection dropped, show reconnecting overlay and return
            if self._connection_lost:
                self._render_reconnecting()
                self.network.stop()
                return   # signal to mainClient that we need a new socket

            self._render_current_view()

        # User closed window
        self.network.stop()
        pygame.quit()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_current_view(self) -> None:
        screen = self.model.current_screen
        view = self.views.get(screen)
        if view:
            if screen in ["lobby", "game", "victory"]:
                view.render(self.model,
                            chat_input=self.controller.get_chat_input(),
                            chat_active=self.controller.is_chat_active())
            else:
                view.render(self.model)

    def _render_reconnecting(self) -> None:
        """Draw a simple 'Reconnecting...' overlay on the current frame."""
        # Dim the screen
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        font_big   = pygame.font.SysFont("Arial", 36, bold=True)
        font_small = pygame.font.SysFont("Arial", 20)

        w, h = self.screen.get_size()
        text1 = font_big.render("Connection Lost", True, (255, 80, 80))
        text2 = font_small.render("Waiting for server to come back...", True, (220, 220, 220))
        text3 = font_small.render("Press Ctrl+C in the terminal to quit", True, (160, 160, 160))

        self.screen.blit(text1, text1.get_rect(center=(w // 2, h // 2 - 40)))
        self.screen.blit(text2, text2.get_rect(center=(w // 2, h // 2 + 10)))
        self.screen.blit(text3, text3.get_rect(center=(w // 2, h // 2 + 40)))
        pygame.display.flip()
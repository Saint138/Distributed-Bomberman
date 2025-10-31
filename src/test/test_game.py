"""
Test suite for the GameState and GameController classes of the client
"""
import unittest
import sys
import os
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pygame
from client.model.game_state import GameState
from client.controller.game_controller import GameController


class TestGameState(unittest.TestCase):
    """Test for GameState model of the client"""

    def setUp(self):
        """Setup for each test"""
        self.game_state = GameState()

    def test_initial_state(self):
        """Test initial state"""
        self.assertIsNone(self.game_state.state)
        self.assertIsNone(self.game_state.player_id)
        self.assertFalse(self.game_state.is_spectator)
        self.assertEqual(self.game_state.player_name, "")
        self.assertEqual(self.game_state.current_screen, "connecting")

    def test_update_state_lobby(self):
        """Test update state to lobby"""
        new_state = {
            "game_state": "lobby",
            "players": {"0": {"name": "Player0", "disconnected": False}},
            "spectators": {},
            "chat_messages": []
        }
        self.game_state.update(new_state)
        self.assertEqual(self.game_state.state, new_state)
        self.assertEqual(self.game_state.current_screen, "lobby")

    def test_update_state_playing(self):
        """Test update state to playing"""
        new_state = {
            "game_state": "playing",
            "map": [[0] * 15 for _ in range(13)],
            "bombs": [],
            "explosions": []
        }
        self.game_state.update(new_state)
        self.assertEqual(self.game_state.current_screen, "game")

    def test_update_state_victory(self):
        """Test update state to victory"""
        new_state = {
            "game_state": "victory",
            "winner_id": 0,
            "victory_timer": 50
        }
        self.game_state.update(new_state)
        self.assertEqual(self.game_state.current_screen, "victory")

    def test_set_player_info(self):
        """Test setting player info"""
        self.game_state.set_player_info(0, False, "TestPlayer")
        self.assertEqual(self.game_state.player_id, 0)
        self.assertFalse(self.game_state.is_spectator)
        self.assertEqual(self.game_state.player_name, "TestPlayer")
        self.assertEqual(self.game_state.current_screen, "lobby")

    def test_get_players(self):
        """Test obtaining players list"""
        test_players = {"0": {"name": "Player0"}, "1": {"name": "Player1"}}
        self.game_state.state = {"players": test_players}
        players = self.game_state.get_players()
        self.assertEqual(players, test_players)

    def test_get_spectators(self):
        """Test obtaining spectators list"""
        test_spectators = {"100": {"name": "Spectator1"}}
        self.game_state.state = {"spectators": test_spectators}
        spectators = self.game_state.get_spectators()
        self.assertEqual(spectators, test_spectators)

    def test_get_chat_messages(self):
        """Test obtaining chat messages"""
        test_messages = [
            {"player_id": 0, "message": "Hello", "is_system": False},
            {"player_id": -1, "message": "System", "is_system": True}
        ]
        self.game_state.state = {"chat_messages": test_messages}
        messages = self.game_state.get_chat_messages()
        self.assertEqual(messages, test_messages)

    def test_is_host(self):
        """Test verify if player is host"""
        self.game_state.player_id = 0
        self.game_state.is_spectator = False
        self.game_state.state = {"current_host_id": 0}
        self.assertTrue(self.game_state.is_host())
        self.game_state.is_spectator = True
        self.assertFalse(self.game_state.is_host())
        self.game_state.is_spectator = False
        self.game_state.player_id = 1
        self.assertFalse(self.game_state.is_host())

    def test_can_start_game(self):
        """Test verify if game can be started"""
        self.game_state.state = {"can_start": True}
        self.assertTrue(self.game_state.can_start_game())
        self.game_state.state = {"can_start": False}
        self.assertFalse(self.game_state.can_start_game())

    def test_connected_players_count(self):
        """Test counting connected players"""
        self.game_state.state = {
            "players": {
                "0": {"disconnected": False},
                "1": {"disconnected": True},
                "2": {"disconnected": False}
            }
        }
        count = self.game_state.connected_players_count()
        self.assertEqual(count, 2)  # Solo i non disconnessi

    def test_get_winner_id(self):
        """Test obtaining winner ID"""
        self.game_state.state = {"winner_id": 0}
        self.assertEqual(self.game_state.get_winner_id(), 0)
        self.game_state.state = {"winner_id": -1}  # Pareggio
        self.assertEqual(self.game_state.get_winner_id(), -1)

    def test_get_map(self):
        """Test obtaining game map"""
        test_map = [[0] * 15 for _ in range(13)]
        self.game_state.state = {"map": test_map}
        game_map = self.game_state.get_map()
        self.assertEqual(game_map, test_map)

    def test_get_bombs(self):
        """Test obtaining bombs"""
        test_bombs = [
            {"x": 5, "y": 5, "timer": 20, "owner": 0}
        ]
        self.game_state.state = {"bombs": test_bombs}
        bombs = self.game_state.get_bombs()
        self.assertEqual(bombs, test_bombs)

    def test_get_explosions(self):
        """Test obtaining explosions"""
        test_explosions = [
            {"positions": [(5, 5), (5, 6)], "timer": 5}
        ]
        self.game_state.state = {"explosions": test_explosions}
        explosions = self.game_state.get_explosions()
        self.assertEqual(explosions, test_explosions)


class TestGameController(unittest.TestCase):
    """Test for GameController of the client"""

    def setUp(self):
        """Setup for each test"""
        pygame.init()
        self.mock_network = Mock()
        self.controller = GameController(self.mock_network)
        self.game_state = Mock()
        self.game_state.current_screen = "lobby"
        self.game_state.is_spectator = False

    def tearDown(self):
        """Cleanup after each test"""
        pygame.quit()

    def test_initial_state(self):
        """Test initial state of controller"""
        self.assertEqual(self.controller.chat_input, "")
        self.assertFalse(self.controller.chat_active)
        self.assertEqual(self.controller.network, self.mock_network)

    def test_handle_quit_event(self):
        """Test handle quit event"""
        event = Mock()
        event.type = pygame.QUIT
        result = self.controller.handle_event(event, self.game_state)
        self.assertFalse(result)

    def test_activate_chat(self):
        """Test chat activation"""
        self.controller._activate_chat()
        self.assertTrue(self.controller.chat_active)
        self.assertEqual(self.controller.chat_input, "")

    def test_handle_chat_activation(self):
        """Test chat activation on 'T' key press"""
        event = Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_t
        self.controller._handle_keydown(event, self.game_state)
        self.assertTrue(self.controller.chat_active)

    def test_handle_chat_input_text(self):
        """Test input text in chat"""
        self.controller.chat_active = True
        event = Mock()
        event.key = pygame.K_a
        event.unicode = "a"
        self.controller._handle_chat_input(event)
        self.assertEqual(self.controller.chat_input, "a")

    def test_handle_chat_input_backspace(self):
        """Test backspace in chat input"""
        self.controller.chat_active = True
        self.controller.chat_input = "test"
        event = Mock()
        event.key = pygame.K_BACKSPACE
        self.controller._handle_chat_input(event)
        self.assertEqual(self.controller.chat_input, "tes")

    def test_handle_chat_input_enter(self):
        """Test sending chat message with ENTER"""
        self.controller.chat_active = True
        self.controller.chat_input = "Hello world"
        event = Mock()
        event.key = pygame.K_RETURN
        self.controller._handle_chat_input(event)
        self.mock_network.send_command.assert_called_once_with("CHAT:Hello world")
        self.assertEqual(self.controller.chat_input, "")
        self.assertFalse(self.controller.chat_active)

    def test_handle_chat_input_escape(self):
        """Test cancelling chat with ESCAPE"""
        self.controller.chat_active = True
        self.controller.chat_input = "test"
        event = Mock()
        event.key = pygame.K_ESCAPE
        self.controller._handle_chat_input(event)
        self.assertEqual(self.controller.chat_input, "")
        self.assertFalse(self.controller.chat_active)

    def test_handle_lobby_input_spectator_join(self):
        """Test spectator that joins the game"""
        self.game_state.is_spectator = True
        self.game_state.connected_players_count.return_value = 2
        event = Mock()
        event.key = pygame.K_j
        self.controller._handle_lobby_input(event, self.game_state)
        self.mock_network.send_command.assert_called_once_with("JOIN_GAME")

    def test_handle_lobby_input_host_start(self):
        """Test host that starts the game"""
        self.game_state.is_spectator = False
        self.game_state.is_host.return_value = True
        self.game_state.can_start_game.return_value = True
        event = Mock()
        event.key = pygame.K_RETURN
        self.controller._handle_lobby_input(event, self.game_state)
        self.mock_network.send_command.assert_called_once_with("START_GAME")

    def test_handle_game_input_movement(self):
        """Test input for player movement"""
        self.game_state.is_spectator = False
        self.game_state.get_game_state.return_value = "playing"
        event = Mock()
        event.key = pygame.K_UP
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_called_with("UP")
        event.key = pygame.K_DOWN
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_called_with("DOWN")
        event.key = pygame.K_LEFT
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_called_with("LEFT")
        event.key = pygame.K_RIGHT
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_called_with("RIGHT")

    def test_handle_game_input_bomb(self):
        """Test bomb placement input"""
        self.game_state.is_spectator = False
        self.game_state.get_game_state.return_value = "playing"
        event = Mock()
        event.key = pygame.K_SPACE
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_called_once_with("BOMB")

    def test_handle_game_input_spectator(self):
        """Test spectator input during game"""
        self.game_state.is_spectator = True
        self.game_state.get_game_state.return_value = "playing"
        event = Mock()
        event.key = pygame.K_SPACE
        self.controller._handle_game_input(event, self.game_state)
        self.mock_network.send_command.assert_not_called()

    def test_handle_victory_input_play_again(self):
        """Test input to play again after victory"""
        self.game_state.is_spectator = False
        event = Mock()
        event.key = pygame.K_RETURN
        self.controller._handle_victory_input(event, self.game_state)
        self.mock_network.send_command.assert_called_once_with("PLAY_AGAIN")

    def test_get_chat_input(self):
        """Test obtaining chat input"""
        self.controller.chat_input = "test message"
        result = self.controller.get_chat_input()
        self.assertEqual(result, "test message")

    def test_is_chat_active(self):
        """Test verify if chat is active"""
        self.controller.chat_active = True
        self.assertTrue(self.controller.is_chat_active())
        self.controller.chat_active = False
        self.assertFalse(self.controller.is_chat_active())

if __name__ == '__main__':
    unittest.main()
"""
Test suite for CommandController and NetworkManager classes.
"""
import unittest
import sys
import os
import socket
import json
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.controller.command_controller import CommandController
from client.network.client_network import NetworkManager


class TestCommandController(unittest.TestCase):
    """Test for CommandController"""

    def setUp(self):
        """Setup for each test"""
        self.mock_game_service = Mock()
        self.mock_game_service.state = Mock()
        self.mock_game_service.state.game_state = "lobby"
        self.player_slots = [False, False, False, False]
        self.controller = CommandController(self.mock_game_service, self.player_slots)

    def test_handle_ping_command(self):
        """Test PING command"""
        response = self.controller.handle_command("PING", 0, False, "Player0")
        self.assertEqual(response, {"type": "pong"})

    def test_handle_empty_command(self):
        """Test empty command"""
        response = self.controller.handle_command("", 0, False, "Player0")
        self.assertEqual(response, {})

    def test_handle_player_movement_commands(self):
        """Test player movement commands"""
        commands = ["UP", "DOWN", "LEFT", "RIGHT"]
        for command in commands:
            response = self.controller.handle_command(command, 0, False, "Player0")
            self.mock_game_service.move_player.assert_called_with(0, command)
            self.assertEqual(response, {})

    def test_handle_player_bomb_command(self):
        """Test bomb placement command"""
        response = self.controller.handle_command("BOMB", 0, False, "Player0")
        self.mock_game_service.place_bomb.assert_called_once_with(0)
        self.assertEqual(response, {})

    def test_handle_start_game_command_as_host(self):
        """Test start game command as host"""
        self.mock_game_service.get_current_host.return_value = 0
        self.mock_game_service.start_game.return_value = True
        response = self.controller.handle_command("START_GAME", 0, False, "Player0")
        self.mock_game_service.start_game.assert_called_once()
        self.assertEqual(response, {})

    def test_handle_start_game_command_not_host(self):
        """Test start game command when not host"""
        self.mock_game_service.get_current_host.return_value = 1  # Un altro è host
        response = self.controller.handle_command("START_GAME", 0, False, "Player0")
        self.mock_game_service.start_game.assert_not_called()
        self.assertEqual(response, {})

    def test_handle_play_again_command(self):
        """Test play again command"""
        self.mock_game_service.state.game_state = "victory"
        response = self.controller.handle_command("PLAY_AGAIN", 0, False, "Player0")
        self.mock_game_service.return_to_lobby.assert_called_once()
        self.assertEqual(response, {})

    def test_handle_chat_command_player(self):
        """Test chat command from player"""
        response = self.controller.handle_command("CHAT:Hello world", 0, False, "Player0")
        self.mock_game_service.add_chat_message.assert_called_once_with(0, "Hello world")
        self.assertEqual(response, {})

    def test_handle_chat_command_empty(self):
        """Test chat command with empty message"""
        response = self.controller.handle_command("CHAT:   ", 0, False, "Player0")
        self.mock_game_service.add_chat_message.assert_not_called()
        self.assertEqual(response, {})

    def test_handle_spectator_chat_command(self):
        """Test chat command from spectator"""
        response = self.controller.handle_command("CHAT:Hello from spectator", 100, True, "Spectator100")
        self.mock_game_service.add_chat_message.assert_called_once_with(100, "Hello from spectator")
        self.assertEqual(response, {})

    def test_handle_spectator_join_game_success(self):
        """Test spectator joins game successfully"""
        self.mock_game_service.state.game_state = "lobby"
        self.mock_game_service.convert_spectator_to_player.return_value = 2  # Nuovo player ID
        response = self.controller.handle_command("JOIN_GAME", 100, True, "Spectator100")
        self.mock_game_service.convert_spectator_to_player.assert_called_once_with(100, "Spectator100")
        self.assertTrue(self.player_slots[2])  # Slot 2 ora occupato
        self.assertEqual(response["type"], "conversion")
        self.assertTrue(response["success"])
        self.assertEqual(response["new_player_id"], 2)

    def test_handle_spectator_join_game_failure(self):
        """Test spectator fails to join game"""
        self.mock_game_service.state.game_state = "lobby"
        self.mock_game_service.convert_spectator_to_player.return_value = -1  # Fallimento
        response = self.controller.handle_command("JOIN_GAME", 100, True, "Spectator100")
        self.assertEqual(response["type"], "conversion")
        self.assertFalse(response["success"])

    def test_handle_spectator_join_game_not_in_lobby(self):
        """Test specator tries to join game when not in lobby"""
        self.mock_game_service.state.game_state = "playing"
        response = self.controller.handle_command("JOIN_GAME", 100, True, "Spectator100")
        self.mock_game_service.convert_spectator_to_player.assert_not_called()
        self.assertEqual(response, {})

    def test_handle_spectator_movement_ignored(self):
        """Test spectator movement commands are ignored"""
        response = self.controller.handle_command("UP", 100, True, "Spectator100")
        self.mock_game_service.move_player.assert_not_called()
        self.assertEqual(response, {})

    def test_handle_command_case_insensitive(self):
        """Test command handling case is insensitive"""
        response = self.controller.handle_command("bomb", 0, False, "Player0")
        self.mock_game_service.place_bomb.assert_called_with(0)
        response = self.controller.handle_command("BoMb", 1, False, "Player1")
        self.mock_game_service.place_bomb.assert_called_with(1)


class TestNetworkManager(unittest.TestCase):
    """Test for NetworkManager"""

    def setUp(self):
        """Setup for each test"""
        self.mock_socket = Mock(spec=socket.socket)
        self.network = NetworkManager(self.mock_socket)

    def test_initial_state(self):
        """Test initial state"""
        self.assertTrue(self.network.running)
        self.assertIsNone(self.network.on_state_update)
        self.assertIsNone(self.network.on_join_success)
        self.assertIsNone(self.network.on_conversion)

    def test_send_command(self):
        """Test send command"""
        self.network.send_command("TEST_COMMAND")
        self.mock_socket.sendall.assert_called_once_with(b"TEST_COMMAND")

    def test_send_command_error_handling(self):
        """Test error handling in send command"""
        self.mock_socket.sendall.side_effect = OSError("Network error")
        self.network.send_command("TEST_COMMAND")
        self.mock_socket.sendall.assert_called_once()

    @patch('threading.Thread')
    def test_start_receiving(self, mock_thread):
        """Test start receiving thread"""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        self.network.start_receiving()
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_handle_join_success_message(self):
        """Test handle join success message"""
        mock_callback = Mock()
        self.network.on_join_success = mock_callback
        message = json.dumps({
            "join_success": True,
            "player_id": 0,
            "is_spectator": False,
            "player_name": "TestPlayer"
        })
        self.network._handle_message(message)
        mock_callback.assert_called_once_with(0, False, "TestPlayer")

    def test_handle_conversion_success_message(self):
        """Test handle conversion success message"""
        mock_callback = Mock()
        self.network.on_conversion = mock_callback
        message = json.dumps({
            "conversion_success": True,
            "new_player_id": 2,
            "is_spectator": False
        })
        self.network._handle_message(message)
        mock_callback.assert_called_once_with(2, False)

    def test_handle_state_update_message(self):
        """Test handle state update message"""
        mock_callback = Mock()
        self.network.on_state_update = mock_callback
        state = {
            "game_state": "lobby",
            "players": {},
            "spectators": {},
            "chat_messages": []
        }
        message = json.dumps(state)
        self.network._handle_message(message)
        mock_callback.assert_called_once_with(state)

    def test_handle_invalid_json(self):
        """Test handle invalid JSON message"""
        self.network._handle_message("invalid json {")
        if self.network.on_state_update:
            self.network.on_state_update.assert_not_called()

    def test_stop_network(self):
        """Test stop network"""
        self.network.stop()
        self.assertFalse(self.network.running)
        self.mock_socket.close.assert_called_once()

    def test_stop_network_error_handling(self):
        """Test error handling in stop network"""
        self.mock_socket.close.side_effect = OSError("Socket already closed")
        self.network.stop()
        self.assertFalse(self.network.running)

    def test_receive_loop_connection_closed(self):
        """Test loop reception when connection is closed"""
        self.mock_socket.recv.return_value = b""
        self.network._receive_loop()
        self.mock_socket.recv.assert_called()

    def test_receive_loop_with_data(self):
        """Test loop reception with data"""
        mock_callback = Mock()
        self.network.on_state_update = mock_callback
        test_data = json.dumps({"game_state": "lobby"}) + "\n"
        self.mock_socket.recv.side_effect = [
            test_data.encode(),
            b""
        ]
        self.network._receive_loop()
        mock_callback.assert_called_once()

    def test_receive_loop_error_handling(self):
        """Test error handling in receive loop"""
        self.mock_socket.recv.side_effect = ConnectionResetError("Connection reset")
        self.network._receive_loop()
        self.mock_socket.recv.assert_called()

if __name__ == '__main__':
    unittest.main()
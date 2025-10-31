"""
Test suite for the GameService class
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.services.game_service import GameService
from server.models import GAME_STATE_LOBBY, GAME_STATE_PLAYING, GAME_STATE_VICTORY


class TestGameService(unittest.TestCase):
    """Test for GameService"""

    def setUp(self):
        """Setup for each test"""
        self.game = GameService()

    def tearDown(self):
        """Cleanup after each test"""
        self.game = None

    def test_add_single_player(self):
        """Test adding a single player"""
        self.game.add_player(0, "TestPlayer")
        self.assertIn(0, self.game.state.players)
        self.assertEqual(self.game.state.players[0].name, "TestPlayer")
        self.assertEqual(self.game.state.current_host_id, 0)

    def test_add_multiple_players(self):
        """Test adding multiple players"""
        for i in range(4):
            self.game.add_player(i, f"Player{i}")
        self.assertEqual(len(self.game.state.players), 4)
        for i in range(4):
            self.assertIn(i, self.game.state.players)

    def test_player_disconnect_in_lobby(self):
        """Test disconnection of player in lobby"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.handle_player_disconnect(0)
        self.assertNotIn(0, self.game.state.players)
        self.assertIn(1, self.game.state.players)
        self.assertEqual(self.game.state.current_host_id, 1)  # Host passa al prossimo

    def test_player_disconnect_in_game(self):
        """Test disconnection of player in game"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.handle_player_disconnect(0)
        self.assertTrue(self.game.state.players[0].disconnected)
        self.assertFalse(self.game.state.players[0].alive)

    def test_add_spectator(self):
        """Test adding a spectator"""
        spectator_id = self.game.add_spectator("Spectator1")
        self.assertIn(spectator_id, self.game.state.spectators)
        self.assertEqual(self.game.state.spectators[spectator_id]["name"], "Spectator1")

    def test_convert_spectator_to_player(self):
        """Test conversion spectator to player"""
        spectator_id = self.game.add_spectator("TestSpectator")
        new_player_id = self.game.convert_spectator_to_player(spectator_id, "TestSpectator")
        self.assertNotIn(spectator_id, self.game.state.spectators)
        self.assertIn(new_player_id, self.game.state.players)
        self.assertEqual(self.game.state.players[new_player_id].name, "TestSpectator")

    def test_convert_spectator_when_full(self):
        """Test conversion spectator to player when all slots are full"""
        for i in range(4):
            self.game.add_player(i, f"Player{i}")
        spectator_id = self.game.add_spectator("Spectator")
        new_player_id = self.game.convert_spectator_to_player(spectator_id)
        self.assertEqual(new_player_id, -1)  # Conversione fallita
        self.assertIn(spectator_id, self.game.state.spectators)  # Spettatore ancora presente

    def test_start_game_success(self):
        """Test game start"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        result = self.game.start_game()
        self.assertTrue(result)
        self.assertEqual(self.game.state.game_state, GAME_STATE_PLAYING)
        self.assertIsNotNone(self.game.state.game_map)
        self.assertTrue(len(self.game.state.game_map) > 0)

    def test_start_game_not_enough_players(self):
        """Test game start with not enough players"""
        self.game.add_player(0, "Player0")
        result = self.game.start_game()
        self.assertFalse(result)
        self.assertEqual(self.game.state.game_state, GAME_STATE_LOBBY)

    def test_return_to_lobby(self):
        """Test return to lobby"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.return_to_lobby()
        self.assertEqual(self.game.state.game_state, GAME_STATE_LOBBY)
        self.assertEqual(len(self.game.state.game_map), 0)
        self.assertEqual(len(self.game.state.bombs), 0)
        self.assertEqual(len(self.game.state.explosions), 0)

    def test_add_chat_message(self):
        """Test add chat message"""
        self.game.add_player(0, "Player0")
        self.game.add_chat_message(0, "Hello world!")
        self.assertEqual(len(self.game.state.chat_messages), 3)
        last_msg = self.game.state.chat_messages[-1]
        self.assertEqual(last_msg["player_id"], 0)
        self.assertEqual(last_msg["message"], "Hello world!")
        self.assertFalse(last_msg["is_system"])

    def test_add_system_message(self):
        """Test add system message"""
        self.game._add_system_message("System message")
        self.assertEqual(len(self.game.state.chat_messages), 1)
        msg = self.game.state.chat_messages[0]
        self.assertEqual(msg["player_id"], -1)
        self.assertTrue(msg["is_system"])

    def test_move_player(self):
        """Test player movement"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        initial_x = self.game.state.players[0].x
        initial_y = self.game.state.players[0].y
        self.game.move_player(0, "DOWN")
        self.assertIn(0, self.game.state.players)

    def test_place_bomb(self):
        """Test bomb placement"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.place_bomb(0)
        self.assertEqual(len(self.game.state.bombs), 1)
        bomb = self.game.state.bombs[0]
        self.assertEqual(bomb.owner, 0)
        self.assertEqual(bomb.x, self.game.state.players[0].x)
        self.assertEqual(bomb.y, self.game.state.players[0].y)

    def test_check_victory_one_player_alive(self):
        """Test verify victory with one player alive"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.state.players[1].alive = False
        self.game.state.players[1].lives = 0
        has_winner = self.game.check_victory()
        self.assertTrue(has_winner)
        self.assertEqual(self.game.state.winner_id, 0)
        self.assertEqual(self.game.state.game_state, GAME_STATE_VICTORY)

    def test_check_victory_draw(self):
        """Test verify victory with all players eliminated (draw)"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        for player in self.game.state.players.values():
            player.alive = False
            player.lives = 0
        has_winner = self.game.check_victory()
        self.assertTrue(has_winner)
        self.assertEqual(self.game.state.winner_id, -1)
        self.assertEqual(self.game.state.game_state, GAME_STATE_VICTORY)

    def test_tick_in_lobby(self):
        """Test tick when in lobby"""
        self.game.add_player(0, "Player0")
        self.game.tick()
        self.assertEqual(self.game.state.game_state, GAME_STATE_LOBBY)

    def test_tick_bomb_explosion(self):
        """Test tick with bomb explosion"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.place_bomb(0)
        self.game.state.bombs[0].timer = 1
        self.game.tick()
        self.assertEqual(len(self.game.state.bombs), 0)
        self.assertEqual(len(self.game.state.explosions), 1)

    def test_tick_victory_timer(self):
        """Test tick with victory timer"""
        self.game.add_player(0, "Player0")
        self.game.add_player(1, "Player1")
        self.game.start_game()
        self.game.state.game_state = GAME_STATE_VICTORY
        self.game.state.victory_timer = 1
        self.game.tick()
        self.assertEqual(self.game.state.game_state, GAME_STATE_LOBBY)


if __name__ == '__main__':
    unittest.main()
"""
Test suite for core module in the Bomberman server.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server import core
from server.models import (
    State, Bomb, Explosion,
    GAME_STATE_LOBBY, GAME_STATE_VICTORY,
    MAP_WIDTH, MAP_HEIGHT, TILE_EMPTY, TILE_WALL, TILE_BLOCK,
    BOMB_TIMER_TICKS
)


class TestCore(unittest.TestCase):
    """Test for core module functions"""

    def setUp(self):
        """Setup a fresh game state before each test"""
        self.state = State()

    def test_get_safe_zones(self):
        """Test safe zones calculation"""
        safe_zones = core.get_safe_zones()
        self.assertGreater(len(safe_zones), 0)
        self.assertIn((1, 1), safe_zones)
        self.assertIn((1, MAP_HEIGHT-2), safe_zones)
        self.assertIn((MAP_WIDTH-2, 1), safe_zones)
        self.assertIn((MAP_WIDTH-2, MAP_HEIGHT-2), safe_zones)

    def test_spawn_for(self):
        """Test spawn point calculation"""
        spawns = [core.spawn_for(i) for i in range(4)]
        self.assertEqual(len(set(spawns)), 4)
        expected_spawns = [
            (1, 1),
            (1, MAP_HEIGHT-2),
            (MAP_WIDTH-2, 1),
            (MAP_WIDTH-2, MAP_HEIGHT-2)
        ]
        for spawn in spawns:
            self.assertIn(spawn, expected_spawns)

    def test_connected_players_count(self):
        """Test counting connected players"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        self.assertEqual(core.connected_players_count(self.state), 2)
        self.state.players[0].disconnected = True
        self.assertEqual(core.connected_players_count(self.state), 1)

    def test_can_spectator_join(self):
        """Test verifying if a spectator can join"""
        self.assertTrue(core.can_spectator_join(self.state))
        for i in range(4):
            core.add_player(self.state, i, f"Player{i}")
        self.assertFalse(core.can_spectator_join(self.state))

    def test_add_chat(self):
        """Test adding chat messages"""
        core.add_chat(self.state, 0, "Test message")
        self.assertEqual(len(self.state.chat_messages), 1)
        msg = self.state.chat_messages[0]
        self.assertEqual(msg["player_id"], 0)
        self.assertEqual(msg["message"], "Test message")
        self.assertFalse(msg["is_system"])
        core.add_chat(self.state, -1, "System message", is_system=True)
        self.assertEqual(len(self.state.chat_messages), 2)
        sys_msg = self.state.chat_messages[1]
        self.assertTrue(sys_msg["is_system"])

    def test_get_current_host(self):
        """Test getting current host"""
        core.add_player(self.state, 1, "Player1")
        core.add_player(self.state, 0, "Player0")
        host = core.get_current_host(self.state)
        self.assertEqual(host, 0)
        self.state.players[0].disconnected = True
        host = core.get_current_host(self.state)
        self.assertEqual(host, 1)

    def test_generate_map(self):
        """Test map generation"""
        game_map = core.generate_map()
        self.assertEqual(len(game_map), MAP_HEIGHT)
        self.assertEqual(len(game_map[0]), MAP_WIDTH)
        for x in range(MAP_WIDTH):
            self.assertEqual(game_map[0][x], TILE_WALL)
            self.assertEqual(game_map[MAP_HEIGHT-1][x], TILE_WALL)
        for y in range(MAP_HEIGHT):
            self.assertEqual(game_map[y][0], TILE_WALL)
            self.assertEqual(game_map[y][MAP_WIDTH-1], TILE_WALL)
        safe_zones = core.get_safe_zones()
        for x, y in safe_zones:
            self.assertNotEqual(game_map[y][x], TILE_BLOCK)

    def test_is_walkable(self):
        """Test verify if tile is walkable"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        self.state.game_map[5][5] = TILE_EMPTY
        self.assertTrue(core.is_walkable(self.state, 5, 5))
        self.state.game_map[5][5] = TILE_WALL
        self.assertFalse(core.is_walkable(self.state, 5, 5))
        self.assertFalse(core.is_walkable(self.state, -1, 0))
        self.assertFalse(core.is_walkable(self.state, MAP_WIDTH, 0))

    def test_is_player_at(self):
        """Test verify if player is at position"""
        core.add_player(self.state, 0, "Player0")
        x, y = self.state.players[0].x, self.state.players[0].y
        self.assertTrue(core.is_player_at(self.state, x, y))
        self.assertFalse(core.is_player_at(self.state, x+1, y+1))
        self.assertFalse(core.is_player_at(self.state, x, y, exclude_id=0))

    def test_move_player(self):
        """Test player movement"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        player = self.state.players[0]
        initial_x, initial_y = player.x, player.y
        if initial_y + 1 < MAP_HEIGHT:
            self.state.game_map[initial_y + 1][initial_x] = TILE_EMPTY
        core.move_player(self.state, 0, "DOWN")
        if player.y == initial_y + 1:
            self.assertEqual(player.y, initial_y + 1)
        else:
            self.assertEqual(player.y, initial_y)

    def test_place_bomb(self):
        """Test bomb placement"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        player = self.state.players[0]
        core.place_bomb(self.state, 0)
        self.assertEqual(len(self.state.bombs), 1)
        bomb = self.state.bombs[0]
        self.assertEqual(bomb.x, player.x)
        self.assertEqual(bomb.y, player.y)
        self.assertEqual(bomb.owner, 0)
        self.assertEqual(bomb.timer, BOMB_TIMER_TICKS)

    def test_explode_bomb(self):
        """Test bomb explosion"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        bomb = Bomb(x=5, y=5, timer=0, owner=0)
        self.state.game_map[5][6] = TILE_BLOCK
        core.explode_bomb(self.state, bomb)
        self.assertEqual(len(self.state.explosions), 1)
        explosion = self.state.explosions[0]
        self.assertIn((5, 5), explosion.positions)
        self.assertEqual(self.state.game_map[5][6], TILE_EMPTY)

    def test_explode_bomb_damages_player(self):
        """Test esplosion damages player"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        self.state.players[0].x = 5
        self.state.players[0].y = 5
        initial_lives = self.state.players[0].lives
        bomb = Bomb(x=5, y=5, timer=0, owner=1)
        core.explode_bomb(self.state, bomb)
        self.assertEqual(self.state.players[0].lives, initial_lives - 1)

    def test_check_victory_one_winner(self):
        """Test check victory with one winner"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        self.state.players[1].alive = False
        self.state.players[1].lives = 0
        has_winner = core.check_victory(self.state)
        self.assertTrue(has_winner)
        self.assertEqual(self.state.winner_id, 0)
        self.assertEqual(self.state.game_state, GAME_STATE_VICTORY)

    def test_check_victory_draw(self):
        """Test check victory with draw"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        for player in self.state.players.values():
            player.alive = False
            player.lives = 0
        has_winner = core.check_victory(self.state)
        self.assertTrue(has_winner)
        self.assertEqual(self.state.winner_id, -1)
        self.assertEqual(self.state.game_state, GAME_STATE_VICTORY)

    def test_safe_to_place_block(self):
        """Test verify if safe to place block"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        px, py = self.state.players[0].x, self.state.players[0].y
        self.assertFalse(core.safe_to_place_block(self.state, px, py))
        safe_zones = core.get_safe_zones()
        for x, y in safe_zones:
            self.assertFalse(core.safe_to_place_block(self.state, x, y))

    def test_return_to_lobby(self):
        """Test return to lobby resets state"""
        core.add_player(self.state, 0, "Player0")
        core.add_player(self.state, 1, "Player1")
        core.start_game(self.state)
        core.place_bomb(self.state, 0)
        explosion = Explosion(positions=[(5, 5)], timer=5)
        self.state.explosions.append(explosion)
        core.return_to_lobby(self.state)
        self.assertEqual(self.state.game_state, GAME_STATE_LOBBY)
        self.assertEqual(len(self.state.game_map), 0)
        self.assertEqual(len(self.state.bombs), 0)
        self.assertEqual(len(self.state.explosions), 0)
        self.assertIsNone(self.state.winner_id)
        for player in self.state.players.values():
            self.assertTrue(player.alive)
            self.assertEqual(player.lives, 3)
            self.assertFalse(player.ready)


if __name__ == '__main__':
    unittest.main()
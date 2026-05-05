"""
Tests for the JSON state codec used by primary -> backup replication. """
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.models import (
    State, Player, Bomb, Explosion,
    STATE_VERSION, state_to_dict, state_from_dict,
    GAME_STATE_PLAYING,
)


def _make_state() -> State:
    s = State()
    s.game_state = GAME_STATE_PLAYING
    s.victory_timer = 3
    s.game_map = [[0] * 15 for _ in range(13)]
    s.bombs = [Bomb(x=3, y=4, timer=15, owner=0)]
    s.explosions = [Explosion(positions=[(1, 2), (1, 3), (2, 2)], timer=4)]
    s.players = {
        0: Player(x=1, y=1, name="alice", alive=True, lives=3),
                1: Player(x=13, y=11, name="bob", disconnected=True,
                  disconnect_time=1234567890.0),
    }
    s.spectators = {100: {"name": "spec1", "queue_pos": 0}}
    s.client_player_mapping = {"sess-abc": 0, "sess-def": 1}
    s.block_regen_timer = 42
    return s


class TestStateCodec(unittest.TestCase):
    def test_roundtrip_preserves_full_state(self):
        s = _make_state()
        encoded = json.dumps(state_to_dict(s)).encode("utf-8")
        decoded = state_from_dict(json.loads(encoded))

        self.assertEqual(decoded.bombs, s.bombs)
        self.assertEqual(decoded.players[0].name, "alice")
        self.assertTrue(decoded.players[1].disconnected)
        self.assertEqual(decoded.block_regen_timer, 42)

    def test_player_dict_keys_remain_int(self):
        """JSON forces string keys; the codec must convert them back."""
        decoded = state_from_dict(json.loads(json.dumps(state_to_dict(_make_state()))))
        for k in decoded.players.keys():
            self.assertIsInstance(k, int)

    def test_explosion_positions_are_tuples(self):
        """Tuples are encoded as JSON arrays; the codec rebuilds tuples."""
        decoded = state_from_dict(json.loads(json.dumps(state_to_dict(_make_state()))))
        for pos in decoded.explosions[0].positions:
            self.assertIsInstance(pos, tuple)

    def test_rejects_unknown_version(self):
        """A snapshot with the wrong version must be refused."""
        with self.assertRaises(ValueError):
            state_from_dict({"version": 999})


if __name__ == "__main__":
    unittest.main()
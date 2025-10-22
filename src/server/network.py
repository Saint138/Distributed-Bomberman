import json
import socket
from typing import List, Optional
from .models import GAME_STATE_LOBBY, GAME_STATE_VICTORY


def handle_client(
        conn: socket.socket,
        addr: tuple,
        clients: List[socket.socket],
        game,  # GameServer type
        user_id: int,
        is_spectator: bool = False,
        player_slots: Optional[List[bool]] = None,
        player_name: str = ""
) -> None:
    """Handles client socket communication and translates messages to game server calls"""
    user_type = "Spectator" if is_spectator else "Player"
    display_name = player_name or f"{user_type} {user_id}"
    print(f"[HANDLER] start {user_type} {user_id} ({display_name}) from {addr}")

    try:
        while True:
            try:
                data = conn.recv(1024)
            except (socket.error, OSError) as e:
                print(f"[HANDLER] Socket error receiving data: {e}")
                break

            if not data:
                break

            try:
                message = data.decode("utf-8").strip()
            except UnicodeDecodeError as e:
                print(f"[HANDLER] Unicode decode error: {e}")
                continue

            if not message:
                continue

            if message == "PING":
                try:
                    conn.sendall(b"PONG\n")
                except (socket.error, OSError) as e:
                    print(f"[HANDLER] Error sending PONG: {e}")
                    break
                continue

            msg_u = message.upper()

            # Handle spectator commands
            if is_spectator:
                if message.startswith("CHAT:"):
                    chat = message[5:]
                    if chat.strip():
                        game.add_chat_message(user_id, chat)
                elif msg_u == "JOIN_GAME":
                    if game.s.game_state == GAME_STATE_LOBBY:
                        spec_name = player_name or f"Spectator {user_id}"
                        new_pid = game.convert_spectator_to_player(user_id, spec_name)
                        if new_pid >= 0:
                            print(f"[CONVERT] Spectator {user_id} -> Player {new_pid}")
                            is_spectator = False
                            user_type = "Player"
                            user_id = new_pid
                            if player_slots is not None:
                                player_slots[new_pid] = True
                            resp = json.dumps({
                                "conversion_success": True,
                                "new_player_id": new_pid,
                                "is_spectator": False
                            })
                            try:
                                conn.sendall((resp + "\n").encode())
                            except (socket.error, OSError) as e:
                                print(f"[HANDLER] Error sending conversion response: {e}")
                                break
                        else:
                            try:
                                conn.sendall(b'{"conversion_success": false}\n')
                            except (socket.error, OSError) as e:
                                print(f"[HANDLER] Error sending conversion failure: {e}")
                                break
                continue

            # Handle player commands
            if msg_u in ("UP", "DOWN", "LEFT", "RIGHT"):
                game.move_player(user_id, msg_u)
                continue

            if msg_u == "BOMB":
                game.place_bomb(user_id)
                continue

            if msg_u == "START_GAME":
                if game.s.game_state == GAME_STATE_LOBBY and user_id == game.get_current_host():
                    if game.start_game():
                        print(f"[GAME] Player {user_id} ({display_name}) started the game")
                continue

            if msg_u == "PLAY_AGAIN":
                if game.s.game_state == GAME_STATE_VICTORY:
                    game.return_to_lobby()
                continue

            if message.startswith("CHAT:"):
                chat = message[5:]
                if chat.strip():
                    game.add_chat_message(user_id, chat)

    except ConnectionResetError as e:
        print(f"[HANDLER] Connection reset by peer: {e}")
    except (socket.error, OSError) as e:
        print(f"[HANDLER] Network error: {e}")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[HANDLER] Data parsing error: {e}")
    finally:
        print(f"[HANDLER] Disconnecting {user_type} {user_id} ({display_name}) from {addr}")
        _cleanup_connection(conn, clients, game, user_id, is_spectator, user_type, player_slots)


def _cleanup_connection(
        conn: socket.socket,
        clients: List[socket.socket],
        game,  # GameServer type
        user_id: int,
        is_spectator: bool,
        user_type: str,
        player_slots: Optional[List[bool]]
) -> None:
    """Cleans up connection resources and game state"""
    try:
        conn.close()
    except (socket.error, OSError):
        pass

    if conn in clients:
        try:
            clients.remove(conn)
        except ValueError:
            pass

    if is_spectator or user_type == "Spectator" or (isinstance(user_id, int) and user_id >= 100):
        try:
            game.remove_spectator(user_id)
        except (KeyError, AttributeError) as e:
            print(f"[HANDLER] Spectator remove error: {e}")
    else:
        try:
            if player_slots is not None and isinstance(user_id, int) and 0 <= user_id < 4:
                player_slots[user_id] = False
            game.handle_player_disconnect(user_id)
        except (KeyError, AttributeError, IndexError) as e:
            print(f"[HANDLER] Player disconnect error: {e}")
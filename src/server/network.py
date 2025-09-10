import json

def handle_client(conn, addr, clients, game, user_id, is_spectator=False, player_slots=None, preread_handshake=None):
    """
    Controller socket: traduce i messaggi testuali in chiamate al GameServer.
    """
    user_type = "Spectator" if is_spectator else "Player"
    print(f"[HANDLER] start {user_type} {user_id} from {addr}")

    client_id = None
    try:
        # handshake già letto dal main
        if preread_handshake:
            try:
                hs = json.loads(preread_handshake.decode().strip())
                if hs.get("type") == "handshake":
                    client_id = hs.get("client_id")
                    print(f"[HANDLER] client_id={client_id}")
            except Exception as e:
                print(f"[HANDLER] handshake parse error: {e}")

        # riconnessione del player (se necessario)
        if not is_spectator and user_id in game.s.players:
            if game.s.players[user_id].disconnected:
                if game.reconnect_player(user_id, client_id):
                    print(f"[HANDLER] Player {user_id} successfully reconnected")
                else:
                    print(f"[HANDLER] Failed to reconnect player {user_id}")
                    conn.close(); return

        # invia identità al client
        init_msg = json.dumps({"player_id": user_id, "is_spectator": is_spectator})
        conn.sendall((init_msg + "\n").encode())

        # loop principale
        while True:
            data = conn.recv(1024)
            if not data:
                break
            try:
                message = data.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue
            if not message:
                continue

            if message == "PING":
                conn.sendall(b"PONG\n")
                continue

            msgU = message.upper()

            # --- Spettatore ---
            if is_spectator:
                if message.startswith("CHAT:"):
                    chat = message[5:]
                    if chat.strip():
                        game.add_chat_message(user_id, chat)
                elif msgU == "JOIN_GAME":
                    if game.s.game_state == game.S.GAME_STATE_LOBBY:
                        new_pid = game.convert_spectator_to_player(user_id, client_id)
                        if new_pid >= 0:
                            print(f"[CONVERT] Spectator {user_id} -> Player {new_pid}")
                            is_spectator = False
                            user_type = "Player"
                            user_id = new_pid
                            if player_slots is not None:
                                player_slots[new_pid] = True
                            resp = json.dumps({"conversion_success": True, "new_player_id": new_pid, "is_spectator": False})
                            conn.sendall((resp + "\n").encode())
                        else:
                            conn.sendall(b'{"conversion_success": false}\n')
                continue

            # --- Player ---
            if msgU in ("UP", "DOWN", "LEFT", "RIGHT"):
                game.move_player(user_id, msgU)
                continue
            if msgU == "BOMB":
                game.place_bomb(user_id)
                continue
            if msgU == "START_GAME":
                if game.s.game_state == game.S.GAME_STATE_LOBBY and user_id == game.get_current_host():
                    if game.start_game():
                        print(f"[GAME] Player {user_id} started the game")
                continue
            if msgU == "PLAY_AGAIN":
                if game.s.game_state == game.S.GAME_STATE_VICTORY:
                    game.return_to_lobby()
                continue
            if message.startswith("CHAT:"):
                chat = message[5:]
                if chat.strip():
                    game.add_chat_message(user_id, chat)

    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"[HANDLER] Error: {e}")
    finally:
        print(f"[HANDLER] Disconnecting {user_type} {user_id} from {addr}")
        try: conn.close()
        except: pass
        if conn in clients:
            try: clients.remove(conn)
            except ValueError: pass

        if is_spectator or user_type == "Spectator" or (is_spectator and isinstance(user_id, int) and user_id >= 100):
            try: game.remove_spectator(user_id)
            except Exception as e: print(f"[HANDLER] spectator remove error: {e}")
        else:
            try:
                if player_slots is not None and isinstance(user_id, int) and 0 <= user_id < 4:
                    player_slots[user_id] = False
                game.handle_player_disconnect(user_id)
            except Exception as e:
                print(f"[HANDLER] player disconnect error: {e}")

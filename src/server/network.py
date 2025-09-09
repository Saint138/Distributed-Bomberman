import json
import time

def handle_client(conn, addr, clients, game, user_id, is_spectator=False, player_slots=None, preread_handshake=None):
    user_type = "Spectator" if is_spectator else "Player"
    print(f"[HANDLER] Starting handler for {user_type} {user_id} from {addr}")
    
    client_id = None
    
    try:
        # Processa l'handshake
        if preread_handshake:
            try:
                handshake = json.loads(preread_handshake.decode().strip())
                if handshake.get("type") == "handshake":
                    client_id = handshake.get("client_id")
                    # FIXED: Non assegnare direttamente al socket, salva in una variabile
                    print(f"[HANDLER] Client ID: {client_id}")
            except Exception as e:
                print(f"[HANDLER] Error processing handshake: {e}")
        
        # Se è un giocatore che si riconnette, aggiorna il suo stato
        if not is_spectator and user_id in game.players:
            if game.players[user_id].get("disconnected", False):
                if game.reconnect_player(user_id, client_id):
                    print(f"[HANDLER] Player {user_id} successfully reconnected")
                else:
                    print(f"[HANDLER] Failed to reconnect player {user_id}")
                    conn.close()
                    return
        
        # Invia l'ID al client
        init_msg = json.dumps({
            "player_id": user_id,
            "is_spectator": is_spectator
        })
        conn.sendall((init_msg + "\n").encode())

        # Ciclo principale di ricezione comandi
        while True:
            data = conn.recv(1024)
            if not data:
                break
            
            try:
                message = data.decode('utf-8').strip()
            except UnicodeDecodeError:
                continue
            
            message_upper = message.upper()
            
            if is_spectator:
                if message.startswith("CHAT:"):
                    chat_message = message[5:]
                    if chat_message.strip():
                        game.add_chat_message(user_id, chat_message)
                elif message_upper == "JOIN_GAME":
                    if game.game_state == "lobby":
                        # FIXED: Rimuovi il parametro client_id extra
                        new_player_id = game.convert_spectator_to_player(user_id, client_id)
                        if new_player_id >= 0:
                            print(f"[CONVERT] Spectator {user_id} -> Player {new_player_id}")
                            
                            is_spectator = False
                            user_id = new_player_id
                            user_type = "Player"
                            
                            if player_slots is not None:
                                player_slots[new_player_id] = True
                            
                            conversion_msg = json.dumps({
                                "conversion_success": True,
                                "new_player_id": new_player_id,
                                "is_spectator": False
                            })
                            conn.sendall((conversion_msg + "\n").encode())
                        else:
                            print(f"[CONVERT] Failed to convert spectator {user_id}")
            else:
                # Comandi per giocatori
                if message_upper in ["UP", "DOWN", "LEFT", "RIGHT"]:
                    game.move_player(user_id, message_upper)
                elif message_upper == "BOMB":
                    game.place_bomb(user_id)
                elif message_upper == "START_GAME":
                    current_host = game.get_current_host()
                    if user_id == current_host and game.game_state == "lobby":
                        if game.start_game():
                            print(f"[GAME] Player {user_id} started the game")
                elif message_upper == "PLAY_AGAIN":
                    if game.game_state == "victory":
                        game.return_to_lobby()
                elif message.startswith("CHAT:"):
                    chat_message = message[5:]
                    if chat_message.strip():
                        game.add_chat_message(user_id, chat_message)

    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"[HANDLER] Error: {e}")

    finally:
        print(f"[HANDLER] Disconnecting {user_type} {user_id} from {addr}")
        conn.close()
        
        if conn in clients:
            clients.remove(conn)
        
        if user_type == "Spectator" or (is_spectator and user_id >= 100):
            game.remove_spectator(user_id)
        else:
            if player_slots is not None and user_id < 4:
                player_slots[user_id] = False
            game.handle_player_disconnect(user_id)
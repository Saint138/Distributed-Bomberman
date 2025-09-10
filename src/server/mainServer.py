import socket, threading, time, json, os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from server.game import GameServer
from server.network import handle_client

clients = []              # sockets dei player
spectator_clients = []    # sockets degli spettatori
MAX_PLAYERS = 4
player_slots = [False, False, False, False]

game = GameServer()

def get_free_player_slot():
    for i in range(MAX_PLAYERS):
        if not player_slots[i]:
            # slot libero o scaduto timeout di un ex-player
            if (i not in game.s.players) or (
                    game.s.players[i].disconnected and game.s.players[i].disconnect_time_left <= 0
            ):
                return i
    return None

def game_loop():
    cleanup_counter = 0
    while True:
        game.tick()
        cleanup_counter += 1
        if cleanup_counter >= 50:  # ~5s se sleep=0.1
            game.cleanup_client_mappings()
            cleanup_counter = 0

        state = json.dumps(game.get_state()) + "\n"

        for c in list(clients):
            try: c.sendall(state.encode())
            except Exception:
                try: clients.remove(c)
                except ValueError: pass

        for s in list(spectator_clients):
            try: s.sendall(state.encode())
            except Exception:
                try: spectator_clients.remove(s)
                except ValueError: pass

        time.sleep(0.1)

def start_server(host="localhost", port=5555):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen()
    print(f"[SERVER] listening on {host}:{port}")

    threading.Thread(target=game_loop, daemon=True).start()

    while True:
        conn, addr = srv.accept()
        print(f"[NEW CONNECTION] {addr} connecting...")

        # 1) Leggi il primo messaggio per determinare il tipo
        try:
            first_data = conn.recv(1024)
            if not first_data:
                print(f"[ERROR] No data from {addr}")
                conn.close()
                continue

            message = json.loads(first_data.decode().strip())
            message_type = message.get("type")

            if message_type == "session_handshake":
                # È un handshake di sessione, aspetta il join_request
                session_id = message.get("session_id")
                print(f"[HANDSHAKE] Session handshake received: {session_id}")

                # Leggi il join_request successivo
                join_data = conn.recv(1024)
                if not join_data:
                    print(f"[ERROR] No join request after handshake from {addr}")
                    conn.close()
                    continue

                join_message = json.loads(join_data.decode().strip())
                if join_message.get("type") != "join_request":
                    print(f"[ERROR] Expected join_request, got {join_message.get('type')}")
                    conn.close()
                    continue

                player_name = join_message.get("player_name", "").strip()
                client_session_id = join_message.get("session_id", session_id)

            elif message_type == "join_request":
                # Join diretto senza handshake di sessione
                player_name = message.get("player_name", "").strip()
                client_session_id = message.get("session_id", "default")

            else:
                print(f"[ERROR] Unknown message type: {message_type}")
                conn.close()
                continue

        except Exception as e:
            print(f"[ERROR] Failed to parse initial message: {e}")
            try: conn.close()
            except: pass
            continue

        # 2) Valida il nome
        if not player_name or len(player_name) < 2:
            error_response = json.dumps({
                "error": "name_too_short",
                "details": "Name must be at least 2 characters long"
            })
            try:
                conn.sendall((error_response + "\n").encode())
                conn.close()
            except:
                pass
            continue

        # 3) Controlla se il nome è già in uso
        name_taken = False
        for player in game.s.players.values():
            if hasattr(player, 'name') and player.name and player.name.lower() == player_name.lower() and not player.disconnected:
                name_taken = True
                break

        if name_taken:
            error_response = json.dumps({
                "error": "name_taken",
                "details": f"Name '{player_name}' is already in use"
            })
            try:
                conn.sendall((error_response + "\n").encode())
                conn.close()
            except:
                pass
            continue

        # 4) Determina se assegnare come player o spectator
        if game.s.game_state == game.S.GAME_STATE_PLAYING:
            # Partita in corso -> spettatore
            spectator_id = game.add_spectator(player_name)
            spectator_clients.append(conn)

            # Invia conferma di join
            success_response = json.dumps({
                "join_success": True,
                "player_id": spectator_id,
                "is_spectator": True,
                "player_name": player_name
            })
            conn.sendall((success_response + "\n").encode())

            threading.Thread(
                target=handle_client,
                args=(conn, addr, spectator_clients, game, spectator_id, True, None, player_name, client_session_id),
                daemon=True
            ).start()
            print(f"[SPECTATOR] {addr} -> Spectator {spectator_id} ({player_name}) - game in progress")

        else:
            # Siamo in lobby
            free_slot = get_free_player_slot()
            if free_slot is not None:
                # Slot disponibile -> player
                player_slots[free_slot] = True
                game.add_player(free_slot, player_name)
                game.s.players[free_slot].original_client_id = client_session_id
                game.register_client_player(client_session_id, free_slot)

                clients.append(conn)

                # Invia conferma di join
                success_response = json.dumps({
                    "join_success": True,
                    "player_id": free_slot,
                    "is_spectator": False,
                    "player_name": player_name
                })
                conn.sendall((success_response + "\n").encode())

                threading.Thread(
                    target=handle_client,
                    args=(conn, addr, clients, game, free_slot, False, player_slots, player_name, client_session_id),
                    daemon=True
                ).start()
                print(f"[PLAYER] {addr} -> Player {free_slot} ({player_name})")

            else:
                # Lobby piena -> spettatore
                spectator_id = game.add_spectator(player_name)
                spectator_clients.append(conn)

                # Invia conferma di join
                success_response = json.dumps({
                    "join_success": True,
                    "player_id": spectator_id,
                    "is_spectator": True,
                    "player_name": player_name
                })
                conn.sendall((success_response + "\n").encode())

                threading.Thread(
                    target=handle_client,
                    args=(conn, addr, spectator_clients, game, spectator_id, True, None, player_name, client_session_id),
                    daemon=True
                ).start()
                print(f"[SPECTATOR] {addr} -> Spectator {spectator_id} ({player_name}) - lobby full")

if __name__ == "__main__":
    start_server()
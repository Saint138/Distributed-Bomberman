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

        # 1) Leggi handshake
        try:
            handshake_data = conn.recv(1024)
            if not handshake_data:
                print(f"[ERROR] No handshake from {addr}")
                conn.close(); continue
            hs = json.loads(handshake_data.decode().strip())
            if hs.get("type") != "handshake" or not hs.get("client_id"):
                print(f"[ERROR] Invalid handshake from {addr}")
                conn.close(); continue
            client_id = hs["client_id"]
            print(f"[HANDSHAKE] client_id={client_id} from {addr}")
        except Exception as e:
            print(f"[ERROR] handshake read error: {e}")
            try: conn.close()
            except: pass
            continue

        # 2) Tentativo di riconnessione forte
        rec_pid, _ = game.handle_client_handshake(client_id)
        if rec_pid is not None:
            p = game.s.players.get(rec_pid)
            if p and p.disconnected and p.disconnect_time_left > 0 and not p.already_reconnected:
                player_slots[rec_pid] = True
                clients.append(conn)
                threading.Thread(
                    target=handle_client,
                    args=(conn, addr, clients, game, rec_pid, False, player_slots, handshake_data),
                    daemon=True
                ).start()
                print(f"[RECONNECTED] {addr} -> Player {rec_pid}")
                continue
            else:
                print(f"[FAILED] reconnection invalid for client {client_id}")

        # 3) Nuova connessione
        if game.s.game_state == game.S.GAME_STATE_PLAYING:
            # a partita in corso -> spettatore
            spectator_id = game.add_spectator()
            spectator_clients.append(conn)
            threading.Thread(
                target=handle_client,
                args=(conn, addr, spectator_clients, game, spectator_id, True, None, handshake_data),
                daemon=True
            ).start()
            print(f"[SPECTATOR] {addr} -> Spectator {spectator_id} (game in progress)")
            continue

        # siamo in lobby -> prova assegnazione slot player
        free_slot = get_free_player_slot()
        if free_slot is not None:
            player_slots[free_slot] = True
            game.add_player(free_slot)
            # mappa client_id -> player_id
            game.s.players[free_slot].original_client_id = client_id
            game.register_client_player(client_id, free_slot)

            clients.append(conn)
            threading.Thread(
                target=handle_client,
                args=(conn, addr, clients, game, free_slot, False, player_slots, handshake_data),
                daemon=True
            ).start()
            print(f"[PLAYER] {addr} -> Player {free_slot}")
        else:
            spectator_id = game.add_spectator()
            spectator_clients.append(conn)
            threading.Thread(
                target=handle_client,
                args=(conn, addr, spectator_clients, game, spectator_id, True, None, handshake_data),
                daemon=True
            ).start()
            print(f"[SPECTATOR] {addr} -> Spectator {spectator_id} (lobby full)")

if __name__ == "__main__":
    start_server()

# mainServer.py
import socket, threading, time, json, os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from server.network import handle_client
from server.game_logic import GameState

clients = []
spectator_clients = []
MAX_PLAYERS = 4
game = GameState()
player_id_counter = 0
player_slots = [False, False, False, False]

def get_free_player_slot():
    """Trova il primo slot libero per un giocatore."""
    for i in range(MAX_PLAYERS):
        if not player_slots[i]:
            # Verifica anche che non ci sia un player in timeout
            if (i not in game.players or
                (game.players[i].get("disconnected", False) and 
                 game.players[i].get("disconnect_time_left", 0) <= 0)):
                return i
    return None

def game_loop():
    while True:
        game.tick()
        state = json.dumps(game.get_state()) + "\n"
        for c in list(clients):
            try:
                c.sendall(state.encode())
            except Exception:
                try:
                    clients.remove(c)
                except ValueError:
                    pass
        for s in list(spectator_clients):
            try:
                s.sendall(state.encode())
            except Exception:
                try: spectator_clients.remove(s)
                except ValueError: pass
        time.sleep(0.1)

def start_server():
    global player_id_counter
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("localhost", 5555))
    srv.listen()
    print("[SERVER] in ascolto su localhost:5555")

    # Avvia loop di gioco
    threading.Thread(target=game_loop, daemon=True).start()

    # Loop di accept + gestione reconnect/nuovo player
    while True:
        conn, addr = srv.accept()
        print(f"[NEW CONNECTION] {addr} connecting...")
        try:
            handshake_data = conn.recv(1024)
            if not handshake_data:
                print(f"[ERROR] No handshake received from {addr}")
                conn.close(); continue
            hs = json.loads(handshake_data.decode().strip())
            if hs.get("type") != "handshake" or not hs.get("client_id"):
                print(f"[ERROR] Invalid handshake from {addr}")
                conn.close(); continue
            client_id = hs["client_id"]
            print(f"[HANDSHAKE] Client {client_id} from {addr}")
        except Exception as e:
            print(f"[ERROR] Handshake read error from {addr}: {e}")
            try: conn.close()
            except: pass
            continue

        # per ora: sempre player “nuovo”
        free_slot = get_free_player_slot()
        if free_slot is not None:
                # Slot disponibile - FIXED: add_player prende solo player_id
                player_slots[free_slot] = True
                game.add_player(free_slot)  # Rimosso client_id qui
                game.players[free_slot]["original_client_id"] = client_id  # Aggiunto manualmente
                game.register_client_player(client_id, free_slot)
                clients.append(conn)
                threading.Thread(target=handle_client, args=(
                    conn, addr, clients, game, free_slot, False, player_slots, handshake_data
                )).start()
                print(f"[PLAYER] {addr} joined as Player {free_slot}")
        else:
            # Tutti gli slot occupati
            spectator_id = game.add_spectator()
            spectator_clients.append(conn)
            threading.Thread(target=handle_client, args=(
                conn, addr, spectator_clients, game, spectator_id, True, None, handshake_data
            )).start()
            print(f"[SPECTATOR] {addr} joined as Spectator {spectator_id} (lobby full)")




if __name__ == "__main__":
    start_server()

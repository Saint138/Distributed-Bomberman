# mainServer.py
import socket, threading, time, json, os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from server.network import handle_client
from server.game_logic import GameState

clients = []
MAX_PLAYERS = 4
game = GameState()
player_id_counter = 0

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

        # tenta rientro entro 20s
        reconnected = False
        for pid, pdata in list(game.players.items()):
            if pdata.get("disconnected") and pdata.get("disconnect_time"):
                if time.time() - pdata["disconnect_time"] <= 20:
                    print(f"[RECONNECTED] Player {pid} da {addr}")
                    pdata["disconnected"] = False
                    pdata["alive"] = True
                    pdata.pop("disconnect_time", None)
                    clients.append(conn)
                    threading.Thread(
                        target=handle_client,
                        args=(conn, addr, clients, game, pid),
                        daemon=True
                    ).start()
                    reconnected = True
                    break

        if not reconnected:
        # lobby piena? rifiuta SOLO nuovi ingressi (i reconnect passano sopra)
            if len(clients) >= MAX_PLAYERS:
                print("[SERVER] Lobby piena: rifiuto nuovo ingresso da", addr)
                try:
                    conn.close()
                finally:
                    continue

            # nuovo player
            pid = player_id_counter
            player_id_counter += 1
            game.add_player(pid)
            clients.append(conn)
            threading.Thread(
                target=handle_client,
                args=(conn, addr, clients, game, pid),
                daemon=True
            ).start()


if __name__ == "__main__":
    start_server()

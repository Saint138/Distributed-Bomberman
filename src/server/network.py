# server/network.py
import json
from time import time as now 

def handle_client(conn, addr, clients, game, player_id):
    print(f"[NEW] {addr} -> Player {player_id}")
    try:
        # invia il player_id al client
        conn.sendall((json.dumps({"player_id": player_id}) + "\n").encode())

        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode().strip().upper()
            if msg in {"UP","DOWN","LEFT","RIGHT"}:
                game.move_player(player_id, msg)
            elif msg == "BOMB":
                game.place_bomb(player_id)
    except ConnectionResetError:
        pass
    finally:
        print(f"[DISCONNECTED] {addr} (Player {player_id})")
        try:
            clients.remove(conn)
        except ValueError:
            pass
    conn.close()
    if player_id in game.players:
        game.players[player_id]["alive"] = False
        game.players[player_id]["disconnected"] = True
        game.players[player_id]["disconnect_time"] = now()

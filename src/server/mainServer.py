import socket, threading, time, json, os, sys, random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# Aggiungi questa riga per includere la directory padre
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.game import GameServer
from server.network import handle_client

clients = []              # sockets dei player
spectator_clients = []    # sockets degli spettatori
MAX_PLAYERS = 4
player_slots = [False, False, False, False]

game = GameServer()

# Lista di nomi casuali
RANDOM_NAMES = [
    "Bomber", "Blaster", "Dynamite", "Thunder", "Flash", "Storm", "Phoenix",
    "Shadow", "Viper", "Rocket", "Ninja", "Falcon", "Tiger", "Wolf", "Eagle",
    "Hunter", "Warrior", "Knight", "Ranger", "Scout", "Sniper", "Ghost",
    "Phantom", "Mystic", "Raven", "Hawk", "Dragon", "Cobra", "Panther", "Lion",
    "Ace", "Blade", "Cyber", "Echo", "Frost", "Grim", "Hero", "Iron", "Jade",
    "King", "Legend", "Master", "Nova", "Onyx", "Prime", "Quest", "Rebel",
    "Spike", "Titan", "Ultra", "Vector", "Wild", "Xenon", "Yell", "Zero"
]

def generate_unique_name():
    """Genera un nome unico non ancora in uso."""
    used_names = set()
    for player in game.s.players.values():
        if hasattr(player, 'name') and player.name:
            used_names.add(player.name)
    for spectator in game.s.spectators.values():
        if spectator.get("name"):
            used_names.add(spectator["name"])

    # Prova prima con nomi base
    available_names = [name for name in RANDOM_NAMES if name not in used_names]
    if available_names:
        return random.choice(available_names)

    # Se tutti i nomi base sono usati, aggiungi numeri
    for i in range(1, 1000):
        name = f"{random.choice(RANDOM_NAMES)}{i}"
        if name not in used_names:
            return name

    # Fallback estremo
    return f"Player{random.randint(1000, 9999)}"

def get_free_player_slot():
    """Trova slot libero - semplificato senza timeout."""
    for i in range(MAX_PLAYERS):
        if not player_slots[i]:
            # Slot libero
            if i not in game.s.players:
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

        try:
            # Genera un nome casuale unico
            player_name = generate_unique_name()
            client_session_id = f"client_{random.randint(10000, 99999)}_{time.time()}"

            print(f"[AUTO-ASSIGN] Generated name: {player_name}")

            # Determina se assegnare come player o spectator
            if game.s.game_state == "playing":
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

        except Exception as e:
            print(f"[ERROR] Error handling connection from {addr}: {e}")
            try:
                conn.close()
            except:
                pass

if __name__ == "__main__":
    start_server()
import json

def handle_client(conn, addr, clients, game, user_id, is_spectator=False, player_slots=None, preread_handshake=None):
    user_type = "Spectator" if is_spectator else "Player"
    print(f"[HANDLER] start {user_type} {user_id} from {addr}")

    client_id = None
    try:
        if preread_handshake:
            try:
                hs = json.loads(preread_handshake.decode().strip())
                if hs.get("type") == "handshake":
                    client_id = hs.get("client_id")
                    print(f"[HANDLER] client_id={client_id}")
            except Exception as e:
                print(f"[HANDLER] handshake parse error: {e}")

        # manda identità
        conn.sendall((json.dumps({"player_id": user_id, "is_spectator": is_spectator}) + "\n").encode())

        # loop
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
            # in questo step non gestiamo ancora comandi

    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"[HANDLER] error: {e}")
    finally:
        try: conn.close()
        except: pass
        if conn in clients:
            try: clients.remove(conn)
            except ValueError: pass
        print(f"[HANDLER] end {user_type} {user_id} from {addr}")

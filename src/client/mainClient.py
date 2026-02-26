"""
Client entry point - with automatic reconnection on proxy/server failure.

If the proxy crashes while the game is running, the game window stays open
showing a "Connection Lost" overlay. As soon as the proxy comes back, the
client reconnects and the game resumes -- no window flicker, no data loss.
"""
import sys
import os
import socket
import time

current_file = os.path.abspath(__file__)
client_dir = os.path.dirname(current_file)
src_dir = os.path.dirname(client_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from client.game import BombermanClient
from common.constants import DEFAULT_HOST, DEFAULT_PORT

# Seconds between reconnection attempts
RECONNECT_DELAY = 2.0


def try_connect(host: str, port: int, timeout: float = 3.0):
    """Try to open a TCP connection. Returns socket on success, None on failure."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.settimeout(None)
        return sock
    except (ConnectionRefusedError, socket.timeout, OSError):
        try:
            sock.close()
        except Exception:
            pass
        return None


def main():
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port: {sys.argv[2]}, using default {DEFAULT_PORT}")

    # ------------------------------------------------------------------
    # Initial connection (retry until server is up)
    # ------------------------------------------------------------------
    sock = None
    attempt = 0
    while sock is None:
        attempt += 1
        print(f"[CLIENT] Connecting to {host}:{port}... (attempt {attempt})")
        sock = try_connect(host, port)
        if sock is None:
            print(f"[CLIENT] Server not available. Retrying in {RECONNECT_DELAY}s... (Ctrl+C to quit)")
            try:
                time.sleep(RECONNECT_DELAY)
            except KeyboardInterrupt:
                print("\n[CLIENT] Quit by user.")
                sys.exit(0)

    print("[CLIENT] Connected! Starting game...")

    # ------------------------------------------------------------------
    # Create game -- pygame window opens here, stays open for the
    # entire session including reconnections
    # ------------------------------------------------------------------
    game = BombermanClient(sock)

    try:
        while True:
            # run() returns either:
            #   - normally: user closed the window -> exit
            #   - with game.is_disconnected == True: proxy crashed -> reconnect
            game.run()

            if not game.is_disconnected:
                # User closed the window intentionally
                break

            # -----------------------------------------------------------
            # Proxy crashed -- show reconnecting overlay and wait.
            # Keep pumping pygame events so the window stays responsive.
            # -----------------------------------------------------------
            print(f"[CLIENT] Proxy lost. Reconnecting to {host}:{port}...")
            new_sock = None
            reconnect_attempt = 0

            while new_sock is None:
                reconnect_attempt += 1

                import pygame
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        print("[CLIENT] Window closed during reconnect.")
                        pygame.quit()
                        sys.exit(0)

                new_sock = try_connect(host, port)
                if new_sock is None:
                    if reconnect_attempt % 5 == 0:
                        print(f"[CLIENT] Still waiting for proxy... (attempt {reconnect_attempt})")
                    time.sleep(RECONNECT_DELAY)
                else:
                    print(f"[CLIENT] Reconnected after {reconnect_attempt} attempt(s)!")
                    game.reconnect(new_sock)

    except KeyboardInterrupt:
        print("\n[CLIENT] Quit by user.")

    print("[CLIENT] Disconnected.")


if __name__ == '__main__':
    main()
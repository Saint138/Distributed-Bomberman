"""
Client entry point
"""
import sys
import os
import socket

current_file = os.path.abspath(__file__)
client_dir = os.path.dirname(current_file)
src_dir = os.path.dirname(client_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from client.game import BombermanClient
from common.constants import DEFAULT_HOST, DEFAULT_PORT

def main():
    """Main client entry point"""
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port: {sys.argv[2]}, using default {DEFAULT_PORT}")
    print(f"[CLIENT] Connecting to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print("[CLIENT] Connected successfully!")
        game = BombermanClient(sock)
        game.run()
    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to server at {host}:{port}")
        print("        Make sure the server is running.")
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")
    finally:
        print("[CLIENT] Disconnected.")

if __name__ == '__main__':
    main()
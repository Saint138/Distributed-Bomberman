import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import socket
from client.game import BombermanClient

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", 5555))
    game = BombermanClient(sock)
    game.run()

if __name__ == '__main__':
    main()
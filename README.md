# Distributed Bomberman

A real-time, fault-tolerant, multiplayer Bomberman built for the Distributed Systems course
(A.Y. 2024/25, University of Bologna).

Up to four players compete on a shared grid, placing bombs to eliminate opponents. An unlimited
number of spectators can observe the match and are promoted to player (FIFO order) when a slot
frees. The system uses an authoritative game server fronted by a stateless proxy and backed by a
passive replica that takes over transparently on primary failure. Disconnected players have a
20-second grace window to reconnect without losing their character.

## Features

- Real-time gameplay for up to 4 players + unlimited spectators.
- FIFO spectator-to-player promotion when a slot frees.
- 20-second reconnection window with character preservation (lives, position, score).
- Active/passive server replication with automatic failover.
- Pygame GUI client with lobby, gameplay, and victory screens.
- MVC separation: network, protocol, game logic, view.

## Architecture

```
                    +-----------+
                    |  Clients  |
                    +-----+-----+
                          | TCP :5555
                    +-----v-----+
                    |   Proxy   |
                    +-----+-----+
                          | TCP :5556
                +---------v---------+      replication :5557
                |  Primary server   |---------------------->  +-----------+
                |  (game loop +     |                         |  Backup   |
                |   state owner)    |<-----heartbeat :5565--- |  server   |
                +-------------------+                         +-----------+
```

The proxy hides the primary/backup pair from clients. On detected primary failure the backup
is promoted and re-binds the primary's port; the proxy buffers client traffic during the
failover and resumes once the new primary is up. State is replicated as versioned UTF-8 JSON
snapshots every 100 ms.

## Quickstart

### Prerequisites

- Python 3.10 or higher.
- [Poetry](https://python-poetry.org/docs/#installation).

### Install

From the project root:

```bash
poetry install
```

This creates an isolated virtualenv and installs `pygame` plus dev tools.

### Run

The system runs as three processes (start them in any order, but the server first):

```bash
# Terminal 1 — primary server (auto-spawns a backup process)
poetry run bomberman-server

# Terminal 2 — proxy
poetry run bomberman-proxy

# Terminal 3..N — one client per player or spectator
poetry run bomberman-client
```

A match needs at least 2 players to start. From the 5th joiner onward, players enter as spectators
and are promoted to player (FIFO) whenever a slot frees.

### Test

```bash
poetry run pytest src/test
```

## Project structure

```
.
├── pyproject.toml         # Poetry configuration & entry points
├── README.md
├── docs/                  # Design notes
└── src/
    ├── client/            # Pygame client (MVC)
    │   ├── mainClient.py
    │   ├── controller/
    │   ├── model/
    │   ├── network/
    │   └── view/
    ├── common/            # Shared constants
    ├── server/
    │   ├── mainServer.py      # Server entry point (primary or backup)
    │   ├── core.py            # Pure game logic (bombs, explosions, win)
    │   ├── models.py          # Domain dataclasses + JSON replication codec
    │   ├── controller/
    │   ├── services/
    │   ├── network/
    │   └── fault_tolerance/   # Proxy, primary, backup, heartbeat
    └── test/
```

## Authors

- Gioele Santi — [gioele.santi2@studio.unibo.it](mailto:gioele.santi2@studio.unibo.it)
- Giovanni Rinchiuso — [giovanni.rinchiuso@studio.unibo.it](mailto:giovanni.rinchiuso@studio.unibo.it)
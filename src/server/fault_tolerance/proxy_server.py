
import json
import os
import select
import socket
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple


_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
_src  = os.path.join(_root, "src")
for _p in (_root, _src):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common.constants import PROXY_FRONTEND_PORT, PRIMARY_GAME_PORT


class ClientSession:
    """Per-client session metadata captured from server responses."""

    def __init__(self, client_addr: Tuple):
        self.client_addr = client_addr
        self.session_id: Optional[str] = None
        self.player_id: Optional[int] = None
        self.player_name: Optional[str] = None
        self.is_spectator: bool = False

    def __repr__(self):
        return (
            f"Session(addr={self.client_addr}, session={self.session_id}, "
            f"player={self.player_id}, name={self.player_name})"
        )


class TCPProxy:
    """
    Transparent TCP proxy with:
    * Fixed backend port -- no dynamic re-discovery needed
    * Session capture from server's join_success JSON response
    * RECONNECT handshake on backend reconnection after failover
    * Client-side buffering during failover window
    """

    FAILOVER_TIMEOUT = 30.0  

    def __init__(
        self,
        listen_port: int = PROXY_FRONTEND_PORT,
        backend_port: int = PRIMARY_GAME_PORT,
    ):
        self.listen_port = listen_port
        self.backend_port = backend_port
        self.backend_host = "localhost"
        self.running = True
        self._active: Dict[Tuple, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.listen_port))
        srv.listen(20)

        print("=" * 70)
        print("[PROXY] TCP Proxy -- transparent failover")
        print(f"[PROXY] Frontend : 0.0.0.0:{self.listen_port}")
        print(f"[PROXY] Backend  : {self.backend_host}:{self.backend_port}  (FIXED)")
        print(f"[PROXY] Failover timeout: {self.FAILOVER_TIMEOUT}s")
        print("=" * 70)

        threading.Thread(target=self._reap_threads, daemon=True).start()

        try:
            while self.running:
                try:
                    client_sock, addr = srv.accept()
                    self._set_keepalive(client_sock)
                    print(f"[PROXY] New connection from {addr}")
                    t = threading.Thread(
                        target=self._handle_connection,
                        args=(client_sock, addr),
                        daemon=True,
                    )
                    with self._lock:
                        self._active[addr] = t
                    t.start()
                except Exception as exc:
                    if self.running:
                        print(f"[PROXY] Accept error: {exc}")
        except KeyboardInterrupt:
            print("\n[PROXY] Shutting down...")
        finally:
            srv.close()

    def stop(self):
        self.running = False

    def _handle_connection(self, client_sock: socket.socket, addr: Tuple):
        backend_sock = None
        session = ClientSession(addr)
        try:
            backend_sock = self._connect_backend(wait=True)
            if not backend_sock:
                print(f"[PROXY] Could not reach backend for {addr}")
                return
            self._set_keepalive(backend_sock)
            print(f"[PROXY] {addr} <-> backend:{self.backend_port}")
            self._forward(client_sock, backend_sock, session)
        except Exception as exc:
            print(f"[PROXY] Error for {addr}: {exc}")
        finally:
            for s in (backend_sock, client_sock):
                self._safe_close(s)
            print(f"[PROXY] Closed {addr}  (session={session.session_id})")

    def _forward(
        self,
        client_sock: socket.socket,
        backend_sock: socket.socket,
        session: ClientSession,
    ):
        """Forward data both ways; handle backend failures transparently."""
        client_sock.setblocking(False)
        backend_sock.setblocking(False)

        sockets = [client_sock, backend_sock]
        client_buf: List[bytes] = []
        in_failover = False

        while self.running:
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 0.5)
            except Exception:
                break
            for s in exceptional:
                if s is backend_sock and not in_failover:
                    in_failover = True
                    new_be = self._do_failover(backend_sock, session)
                    if new_be:
                        backend_sock = new_be
                        backend_sock.setblocking(False)
                        sockets = [client_sock, backend_sock]
                        self._flush_buf(client_buf, backend_sock)
                        in_failover = False
                    else:
                        return
                elif s is client_sock:
                    return
            for s in readable:
                try:
                    data = s.recv(8192)
                except BlockingIOError:
                    continue
                except OSError:
                    if s is client_sock:
                        return
                    if not in_failover:
                        in_failover = True
                        new_be = self._do_failover(backend_sock, session)
                        if new_be:
                            backend_sock = new_be
                            backend_sock.setblocking(False)
                            sockets = [client_sock, backend_sock]
                            self._flush_buf(client_buf, backend_sock)
                            in_failover = False
                        else:
                            return
                    continue

                if not data:
                    if s is client_sock:
                        return
                    if not in_failover:
                        in_failover = True
                        new_be = self._do_failover(backend_sock, session)
                        if new_be:
                            backend_sock = new_be
                            backend_sock.setblocking(False)
                            sockets = [client_sock, backend_sock]
                            self._flush_buf(client_buf, backend_sock)
                            in_failover = False
                        else:
                            return
                    continue

                if s is client_sock:
                    if in_failover:
                        client_buf.append(data)
                    else:
                        try:
                            backend_sock.sendall(data)
                        except OSError:
                            if not in_failover:
                                client_buf.append(data)
                                in_failover = True
                                new_be = self._do_failover(backend_sock, session)
                                if new_be:
                                    backend_sock = new_be
                                    backend_sock.setblocking(False)
                                    sockets = [client_sock, backend_sock]
                                    self._flush_buf(client_buf, backend_sock)
                                    in_failover = False
                                else:
                                    return
                else:
                    if not session.session_id:
                        self._parse_session(data, session)
                    try:
                        client_sock.sendall(data)
                    except OSError:
                        return


    def _do_failover(
        self, old_backend: socket.socket, session: ClientSession
    ) -> Optional[socket.socket]:
        """
        Wait for the new primary on backend_port, then reconnect.
        Send RECONNECT:<session_id> if a session was captured.
        """
        hint = f" (Player {session.player_id} / {session.player_name})" \
               if session.player_id is not None else ""
        print(
            f"[PROXY] Backend lost{hint} -- "
            f"waiting for new primary on port {self.backend_port}..."
        )
        self._safe_close(old_backend)

        new_sock = self._connect_backend(wait=True, timeout=self.FAILOVER_TIMEOUT)
        if not new_sock:
            print(f"[PROXY] [FAIL] Failover failed after {self.FAILOVER_TIMEOUT}s")
            return None

        self._set_keepalive(new_sock)

        if session.session_id:
            try:
                new_sock.sendall(f"RECONNECT:{session.session_id}\n".encode())
                print(f"[PROXY] Sent RECONNECT:{session.session_id}")
            except Exception as exc:
                print(f"[PROXY] Failed to send RECONNECT: {exc}")

        print(f"[PROXY] [OK] Reconnected to new primary on port {self.backend_port}")
        return new_sock


    def _connect_backend(
        self, wait: bool = False, timeout: float = 15.0
    ) -> Optional[socket.socket]:
        """
        Connect to the fixed backend_port.
        If wait=True, keep retrying for up to `timeout` seconds.
        """
        deadline = time.time() + (timeout if wait else 0.6)
        attempt = 0

        while time.time() < deadline:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect((self.backend_host, self.backend_port))
                s.settimeout(None)
                return s
            except (ConnectionRefusedError, socket.timeout, OSError):
                try:
                    s.close()
                except Exception:
                    pass
                attempt += 1
                if attempt % 20 == 0:
                    print(
                        f"[PROXY] Still waiting for backend on port "
                        f"{self.backend_port}... (attempt {attempt})"
                    )
                time.sleep(0.1)
            except Exception as exc:
                print(f"[PROXY] Unexpected connect error: {exc}")
                time.sleep(0.2)

        return None

    def _parse_session(self, data: bytes, session: ClientSession):
        """Extract session metadata from the server's join_success JSON."""
        try:
            text = data.decode("utf-8", errors="replace")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("join_success"):
                        session.player_id   = msg.get("player_id")
                        session.player_name = msg.get("player_name")
                        session.is_spectator = msg.get("is_spectator", False)

                        if "session_id" in msg:
                            session.session_id = msg["session_id"]
                        elif session.player_id is not None and not session.is_spectator:
                            session.session_id = f"player_{session.player_id}"

                        print(
                            f"[PROXY] Session captured: id={session.session_id}  "
                            f"player={session.player_id} ({session.player_name})  "
                            f"spectator={session.is_spectator}"
                        )
                    elif msg.get("reconnected"):
                        print(
                            f"[PROXY] Reconnect confirmed for player {session.player_id}"
                        )
                except json.JSONDecodeError:
                    pass
        except Exception as exc:
            print(f"[PROXY] Session parse error: {exc}")


    @staticmethod
    def _flush_buf(buf: List[bytes], sock: socket.socket):
        if not buf:
            return
        print(f"[PROXY] Flushing {len(buf)} buffered chunk(s) to new backend")
        for chunk in buf:
            try:
                sock.sendall(chunk)
            except Exception as exc:
                print(f"[PROXY] Flush error: {exc}")
                break
        buf.clear()

    @staticmethod
    def _set_keepalive(sock: socket.socket):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 1000, 500))
        except Exception:
            pass

    @staticmethod
    def _safe_close(sock: Optional[socket.socket]):
        if sock is None:
            return
        for method in ("shutdown", "close"):
            try:
                if method == "shutdown":
                    sock.shutdown(socket.SHUT_RDWR)
                else:
                    sock.close()
            except Exception:
                pass

    def _reap_threads(self):
        """Periodically remove dead thread entries."""
        while self.running:
            time.sleep(10)
            with self._lock:
                dead = [a for a, t in self._active.items() if not t.is_alive()]
                for a in dead:
                    del self._active[a]
                if dead:
                    print(
                        f"[PROXY] Reaped {len(dead)} dead thread(s).  "
                        f"Active: {len(self._active)}"
                    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TCP Proxy for Bomberman fault tolerance")
    parser.add_argument(
        "--listen-port", type=int, default=PROXY_FRONTEND_PORT,
        help=f"Port clients connect to (default: {PROXY_FRONTEND_PORT})",
    )
    parser.add_argument(
        "--backend-port", type=int, default=PRIMARY_GAME_PORT,
        help=f"Fixed backend port (default: {PRIMARY_GAME_PORT})",
    )
    args = parser.parse_args()

    proxy = TCPProxy(listen_port=args.listen_port, backend_port=args.backend_port)
    proxy.start()


if __name__ == "__main__":
    main()
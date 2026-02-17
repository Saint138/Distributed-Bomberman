"""
TCP Proxy for transparent failover with session tracking and reconnect handshake.

When the primary dies:
1. Proxy detects backend disconnect
2. Proxy waits for new primary on FIXED port 5556
3. Once reconnected, proxy sends RECONNECT:<session_id> to new backend
4. New backend (promoted backup) restores the session from its registry
5. Game continues as if nothing happened!
"""
import socket
import threading
import time
import select
import json
from typing import Optional, Tuple, Dict, List


class ClientSession:
    """Tracks session info for a connected client"""
    
    def __init__(self, client_addr: Tuple):
        self.client_addr = client_addr
        self.session_id: Optional[str] = None
        self.player_id: Optional[int] = None
        self.player_name: Optional[str] = None
        self.is_spectator: bool = False
        self.connected = True
    
    def __repr__(self):
        return (f"Session(addr={self.client_addr}, id={self.session_id}, "
                f"player={self.player_id}, name={self.player_name})")


class TCPProxy:
    """
    TCP Proxy that:
    - Forwards client connections to the active primary backend
    - Tracks session info (player_id, session_id) from server responses
    - On backend failure: waits for new primary on FIXED port, then sends
      RECONNECT:<session_id> so the new primary can restore the session
    - Clients stay connected throughout the entire failover!
    """
    
    def __init__(self, listen_port: int = 5555, backend_port: int = 5556):
        self.listen_port = listen_port
        self.backend_port = backend_port    
        self.backend_host = "localhost"
        self.running = True
        self.active_connections: Dict[Tuple, threading.Thread] = {}
        self.connection_lock = threading.Lock()
        
    def start(self):
        """Start the proxy"""
        proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        proxy_socket.bind(("0.0.0.0", self.listen_port))
        proxy_socket.listen(20)
        
        print("=" * 70)
        print("[PROXY] TCP PROXY FOR TRANSPARENT FAILOVER")
        print("=" * 70)
        print(f"[PROXY] Listening on port {self.listen_port}")
        print(f"[PROXY] Backend FIXED on port {self.backend_port}")
        print(f"[PROXY] Session tracking: ENABLED")
        print(f"[PROXY] Reconnect handshake: ENABLED")
        print(f"[PROXY] Max failover wait: 15 seconds")
        print("=" * 70)
        
        threading.Thread(target=self._cleanup_dead_connections, daemon=True).start()
        
        try:
            while self.running:
                try:
                    client_socket, client_addr = proxy_socket.accept()
                    
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
                        client_socket.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 1000, 500))
                    
                    print(f"[PROXY] New connection from {client_addr}")
                    
                    thread = threading.Thread(
                        target=self._handle_connection,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    
                    with self.connection_lock:
                        self.active_connections[client_addr] = thread
                    
                    thread.start()
                    
                except Exception as e:
                    if self.running:
                        print(f"[PROXY] Error accepting connection: {e}")
                        
        except KeyboardInterrupt:
            print("\n[PROXY] Shutting down...")
        finally:
            proxy_socket.close()
            
    def _cleanup_dead_connections(self):
        """Clean up dead connections every 5 seconds"""
        while self.running:
            time.sleep(5)
            with self.connection_lock:
                dead = [addr for addr, t in self.active_connections.items() if not t.is_alive()]
                for addr in dead:
                    del self.active_connections[addr]
                if dead:
                    print(f"[PROXY] Cleaned {len(dead)} dead connections. Active: {len(self.active_connections)}")
            
    def _handle_connection(self, client_socket: socket.socket, client_addr: Tuple):
        """Handle a client connection with session tracking"""
        backend_socket = None
        session = ClientSession(client_addr)
        
        try:
            backend_socket = self._connect_to_backend_fixed()
            
            if not backend_socket:
                print(f"[PROXY] Failed to connect to backend for {client_addr}")
                client_socket.close()
                return
            
            backend_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
                backend_socket.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 1000, 500))
                
            print(f"[PROXY] {client_addr} <-> backend:{self.backend_port} established")
            self._bidirectional_forward(client_socket, backend_socket, client_addr, session)
            
        except Exception as e:
            print(f"[PROXY] Error handling connection from {client_addr}: {e}")
        finally:
            for s in [backend_socket, client_socket]:
                if s:
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    try:
                        s.close()
                    except:
                        pass
            print(f"[PROXY] Connection closed for {client_addr} (session={session.session_id})")
            
    def _connect_to_backend_fixed(self, max_wait: float = 15.0) -> Optional[socket.socket]:
        """
        Connect to FIXED backend port (5556).
        Waits up to max_wait seconds for the backend to be ready.
        """
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < max_wait:
            try:
                backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                backend_socket.settimeout(0.5)
                backend_socket.connect((self.backend_host, self.backend_port))
                backend_socket.settimeout(None)
                return backend_socket
                    
            except (ConnectionRefusedError, socket.timeout, OSError):
                try:
                    backend_socket.close()
                except:
                    pass
                attempt += 1
                if attempt % 10 == 0:
                    print(f"[PROXY] Waiting for backend on port {self.backend_port}... ({attempt})")
                time.sleep(0.1)
            except Exception as e:
                print(f"[PROXY] Unexpected error connecting to backend: {e}")
                time.sleep(0.2)
            
        print(f"[PROXY] Could not connect to backend on port {self.backend_port} after {max_wait}s")
        return None
        
    def _reconnect_to_backend_with_session(self, old_socket: socket.socket,
                                            session: ClientSession,
                                            max_wait: float = 15.0) -> Optional[socket.socket]:
        """
        Reconnect to backend after failover.
        If we have a session_id, send RECONNECT:<session_id> to restore the session.
        """
        print(f"[PROXY] Backend lost! Waiting for new primary on port {self.backend_port}...")
        if session.session_id:
            print(f"[PROXY] Will reconnect session {session.session_id} (Player {session.player_id})")
        
        try:
            old_socket.close()
        except:
            pass
        
        start = time.time()
        attempt = 0
        
        while time.time() - start < max_wait:
            try:
                new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                new_socket.settimeout(0.5)
                new_socket.connect((self.backend_host, self.backend_port))
                new_socket.settimeout(None)
                new_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
                    new_socket.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 1000, 500))
                
                elapsed = time.time() - start
                print(f"[PROXY] Connected to new backend in {elapsed:.2f}s")
                if session.session_id:
                    reconnect_msg = f"RECONNECT:{session.session_id}\n"
                    new_socket.sendall(reconnect_msg.encode())
                    print(f"[PROXY] Sent RECONNECT:{session.session_id}")
                
                
                return new_socket
                
            except (ConnectionRefusedError, socket.timeout, OSError):
                try:
                    new_socket.close()
                except:
                    pass
                attempt += 1
                if attempt % 10 == 0:
                    print(f"[PROXY] Still waiting for new primary... ({attempt} attempts)")
                time.sleep(0.1)
            except Exception as e:
                print(f"[PROXY] Reconnect error: {e}")
                time.sleep(0.2)
        
        print(f"[PROXY] Failover FAILED after {max_wait}s")
        return None

    def _try_parse_session_id_from_response(self, data: bytes, session: ClientSession):
        """
        Parse the session_id from server response.
        The server includes session_id in the join response.
        """
        if not data:
            return
        
        try:
            text = data.decode('utf-8', errors='replace')
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if isinstance(msg, dict) and msg.get('join_success'):
                        session.player_id = msg.get('player_id')
                        session.player_name = msg.get('player_name')
                        session.is_spectator = msg.get('is_spectator', False)
                        
                        if 'session_id' in msg:
                            # Server explicitly sent session_id - best case
                            session.session_id = msg['session_id']
                            print(f"[PROXY] Session: id={session.session_id}, "
                                  f"player={session.player_id} ({session.player_name})")
                        elif session.player_id is not None and not session.is_spectator:
                            # Fallback: build id from player_id
                            session.session_id = f"player_{session.player_id}"
                            print(f"[PROXY] Session (fallback id): player={session.player_id} "
                                  f"({session.player_name}), id={session.session_id}")
                        
                        if msg.get('reconnected'):
                            print(f"[PROXY] Reconnect confirmed by server for player {session.player_id}")
                        
                        return  # Parsed successfully
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"[PROXY] Error parsing session: {e}")

    def _bidirectional_forward(self, client_socket: socket.socket,
                               backend_socket: socket.socket,
                               client_addr: Tuple,
                               session: ClientSession):
        """
        Bidirectional data forwarding with:
        - Session tracking (captures session_id from server response)
        - Data buffering during failover
        - Reconnect handshake on backend reconnection
        """
        client_socket.setblocking(False)
        backend_socket.setblocking(False)
        
        sockets = [client_socket, backend_socket]
    
        client_buffer: List[bytes] = []
        in_failover = False
        
        while self.running:
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 0.5)
                if exceptional:
                    if backend_socket in exceptional and not in_failover:
                        print(f"[PROXY] Backend exception for {client_addr}")
                        in_failover = True
                        new_backend = self._reconnect_to_backend_with_session(
                            backend_socket, session
                        )
                        if new_backend:
                            backend_socket = new_backend
                            backend_socket.setblocking(False)
                            sockets = [client_socket, backend_socket]
                            in_failover = False
                            self._flush_buffer(client_buffer, backend_socket)
                        else:
                            break
                    elif client_socket in exceptional:
                        break
                    continue
                
                for sock in readable:
                    try:
                        data = sock.recv(8192)
                        
                        if not data:
                            if sock is backend_socket and not in_failover:
                                print(f"[PROXY] Backend closed for {client_addr}, starting failover...")
                                in_failover = True
                                new_backend = self._reconnect_to_backend_with_session(
                                    backend_socket, session
                                )
                                if new_backend:
                                    backend_socket = new_backend
                                    backend_socket.setblocking(False)
                                    sockets = [client_socket, backend_socket]
                                    in_failover = False
                                    self._flush_buffer(client_buffer, backend_socket)
                                else:
                                    return
                            elif sock is client_socket:
                                return
                            continue
                        
   
                        if sock is client_socket:
                            if in_failover:
                                client_buffer.append(data)
                            else:
                                try:
                                    backend_socket.sendall(data)
                                except (BrokenPipeError, ConnectionResetError, OSError):
                                    if not in_failover:
                                        client_buffer.append(data)
                                        in_failover = True
                                        new_backend = self._reconnect_to_backend_with_session(
                                            backend_socket, session
                                        )
                                        if new_backend:
                                            backend_socket = new_backend
                                            backend_socket.setblocking(False)
                                            sockets = [client_socket, backend_socket]
                                            in_failover = False
                                            self._flush_buffer(client_buffer, backend_socket)
                                        else:
                                            return
                        else:
                            if not session.session_id:
                                self._try_parse_session_id_from_response(data, session)
                            
                            try:
                                client_socket.sendall(data)
                            except:
                                return
                            
                    except (ConnectionResetError, BrokenPipeError):
                        if sock is backend_socket and not in_failover:
                            print(f"[PROXY] Backend reset for {client_addr}, starting failover...")
                            in_failover = True
                            new_backend = self._reconnect_to_backend_with_session(
                                backend_socket, session
                            )
                            if new_backend:
                                backend_socket = new_backend
                                backend_socket.setblocking(False)
                                sockets = [client_socket, backend_socket]
                                in_failover = False
                                self._flush_buffer(client_buffer, backend_socket)
                            else:
                                return
                        elif sock is client_socket:
                            return
                    except BlockingIOError:
                        continue
                    except Exception as e:
                        if sock is client_socket:
                            return
                        elif not in_failover:
                            print(f"[PROXY] Backend error for {client_addr}: {e}")
                            in_failover = True
                            new_backend = self._reconnect_to_backend_with_session(
                                backend_socket, session
                            )
                            if new_backend:
                                backend_socket = new_backend
                                backend_socket.setblocking(False)
                                sockets = [client_socket, backend_socket]
                                in_failover = False
                                self._flush_buffer(client_buffer, backend_socket)
                            else:
                                return
                        
            except Exception as e:
                print(f"[PROXY] Select error for {client_addr}: {e}")
                break

    def _flush_buffer(self, client_buffer: List[bytes], backend_socket: socket.socket):
        """Send buffered client data to new backend"""
        if client_buffer:
            print(f"[PROXY] Flushing {len(client_buffer)} buffered messages to new backend")
            for buffered_data in client_buffer:
                try:
                    backend_socket.sendall(buffered_data)
                except Exception as e:
                    print(f"[PROXY] Error flushing buffer: {e}")
                    break
            client_buffer.clear()
                
    def stop(self):
        """Stop the proxy"""
        self.running = False


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TCP Proxy for Bomberman Fault Tolerance')
    parser.add_argument('--listen-port', type=int, default=5555)
    parser.add_argument('--backend-port', type=int, default=5556)
    
    args = parser.parse_args()
    
    proxy = TCPProxy(listen_port=args.listen_port, backend_port=args.backend_port)
    proxy.start()


if __name__ == "__main__":
    main()
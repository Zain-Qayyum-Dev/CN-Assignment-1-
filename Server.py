"""
server.py - Multi-client TCP chat server (EE-353 Computer Networks, Assignment 1, Q2)
Author: Muhammad Zain Qayyum - 542221

Protocol: plain text, one message per line (ends with "\n").
  hello everyone   -> broadcast to all other users
  @sara hi         -> private message to sara only
  /users           -> list online users
  /quit            -> leave the chat
  /anything-else   -> "Invalid command" error to the sender only
"""

import socket
import sys
import threading

STUDENT_INFO = "Muhammad Zain Qayyum - 542221"
HOST = "0.0.0.0"          # listen on all network interfaces
PORT = 5000
MAX_NAME_LEN = 20

clients = {}                       # {username: socket} of everyone online
clients_lock = threading.Lock()    # protects the clients dictionary


# ---------------------------------------------------------------- helpers
def get_local_ip():
    """Return this machine's LAN IP (falls back to 127.0.0.1)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))   # no data is sent; just picks the interface
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def send_to(sock, text):
    """Send one line to one client. Returns False if the send failed."""
    try:
        sock.sendall((text + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- messaging
def broadcast_message(message, exclude=None):
    """Send a message to every connected client except `exclude`."""
    with clients_lock:
        targets = [s for name, s in clients.items() if name != exclude]
    for sock in targets:               # send outside the lock so one slow client can't block others
        send_to(sock, message)


def send_private_message(sender, sender_sock, recipient, text):
    """Deliver a private message only to `recipient`."""
    if recipient == sender:
        send_to(sender_sock, "[ERROR]: You cannot message yourself.")
        return
    with clients_lock:
        recipient_sock = clients.get(recipient)
    if recipient_sock is None:
        send_to(sender_sock, f"[ERROR]: User '{recipient}' is not online.")
    elif send_to(recipient_sock, f"[PRIVATE from {sender}]: {text}"):
        send_to(sender_sock, f"[PRIVATE to {recipient}]: {text}")
    else:
        send_to(sender_sock, f"[ERROR]: Could not deliver message to '{recipient}'.")


def send_user_list(sock):
    """Reply to /users with the names of everyone online."""
    with clients_lock:
        names = sorted(clients)
    send_to(sock, "[ONLINE USERS]: " + ", ".join(names))


# ---------------------------------------------------------------- user management
def register_client(sock, reader):
    """Ask for a username until a valid, unique one is given. Returns it, or None if client left."""
    while True:
        send_to(sock, "Enter username:")
        line = reader.readline()
        if not line:                              # client closed before registering
            return None
        name = line.strip()

        if not name:
            send_to(sock, "[ERROR]: Username cannot be empty.")
        elif " " in name or name.startswith(("@", "/")):
            send_to(sock, "[ERROR]: Username cannot contain spaces or start with @ or /.")
        elif len(name) > MAX_NAME_LEN:
            send_to(sock, f"[ERROR]: Username must be at most {MAX_NAME_LEN} characters.")
        else:
            with clients_lock:                    # check + add in one step (no race)
                if name in clients:
                    taken = True
                else:
                    clients[name] = sock
                    taken = False
            if not taken:
                return name
            send_to(sock, f"[ERROR]: Username '{name}' is already taken.")


def remove_client(username, sock):
    """Remove a client, close its socket, and tell everyone else it left."""
    with clients_lock:
        was_online = clients.get(username) is sock
        if was_online:
            del clients[username]
    try:
        sock.close()
    except OSError:
        pass
    if was_online:
        print(f"[-] {username} disconnected")
        broadcast_message(f"{username} has left the chat")


# ---------------------------------------------------------------- per-client logic
def handle_message(username, sock, line):
    """Work out whether a line is a command, a private message or a broadcast.
    Returns False when the client wants to quit."""
    if line == "/quit":
        send_to(sock, "Goodbye!")
        return False
    if line == "/users":
        send_user_list(sock)
    elif line.startswith("/"):
        send_to(sock, "[ERROR]: Invalid command. Use /users, /quit, @username message, or plain text.")
    elif line.startswith("@"):
        parts = line[1:].split(" ", 1)
        if len(parts) < 2 or not parts[0] or not parts[1].strip():
            send_to(sock, "[ERROR]: Usage: @username message")
        else:
            send_private_message(username, sock, parts[0], parts[1].strip())
    else:
        broadcast_message(f"[{username}]: {line}", exclude=username)
    return True


def handle_client(sock, addr):
    """Thread target: one thread runs this for each connected client."""
    username = None
    reader = sock.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    try:
        username = register_client(sock, reader)
        if username is None:
            return
        print(f"[+] {username} connected from {addr[0]}:{addr[1]}")
        send_to(sock, f"Welcome, {username}! Type /users, @name message, or /quit.")
        broadcast_message(f"{username} has joined the chat", exclude=username)

        for line in reader:                       # ends when the client disconnects
            line = line.strip()
            if line and not handle_message(username, sock, line):
                break
    except (OSError, ValueError):
        pass                                      # abrupt disconnect: handled in finally
    finally:
        if username is not None:
            remove_client(username, sock)
        else:
            sock.close()


# ---------------------------------------------------------------- main
def start_server(port):
    """socket -> bind -> listen -> accept loop (one thread per client)."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port))
    server.listen()

    print("=" * 50)
    print(f" Chat Server  |  {STUDENT_INFO}")
    print("=" * 50)
    print(f"Listening on {HOST}:{port}  (LAN IP: {get_local_ip()})")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            client_sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        with clients_lock:
            for sock in clients.values():
                sock.close()
        server.close()


if __name__ == "__main__":
    start_server(int(sys.argv[1]) if len(sys.argv) > 1 else PORT)

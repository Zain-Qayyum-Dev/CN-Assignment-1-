"""
client.py - Chat client (EE-353 Computer Networks, Assignment 1, Q2)
Author: Muhammad Zain Qayyum - 542221

Usage:  python client.py [server_ip] [port]
        (if missing, you will be asked for them)

Type text to broadcast, "@name message" for a private message,
/users to list online users, /quit to leave.
"""

import os
import socket
import sys
import threading

STUDENT_INFO = "Muhammad Zain Qayyum - 542221"
DEFAULT_PORT = 5000


# ---------------------------------------------------------------- receiving
def receive_messages(sock):
    """Thread target: print every line the server sends, until it disconnects."""
    try:
        reader = sock.makefile("r", encoding="utf-8", errors="replace", newline="\n")
        for line in reader:
            print(line.rstrip("\n"), flush=True)
    except (OSError, ValueError):
        pass
    print("\n[Disconnected from server]", flush=True)
    os._exit(0)          # main thread may be blocked in input(), so exit the whole program


# ---------------------------------------------------------------- sending
def send_line(sock, text):
    """Send one line of text to the server."""
    sock.sendall((text + "\n").encode("utf-8"))


def send_messages(sock):
    """Main loop: read what the user types and send it. Ends on /quit."""
    while True:
        try:
            text = input()
        except EOFError:
            text = "/quit"
        if not text.strip():
            continue                       # ignore empty input
        try:
            send_line(sock, text.strip())
        except OSError:
            print("[ERROR]: Connection lost.")
            return
        if text.strip() == "/quit":
            return


# ---------------------------------------------------------------- connection
def get_server_address():
    """Take IP and port from command-line arguments, or ask the user."""
    ip = sys.argv[1] if len(sys.argv) > 1 else input("Server IP: ").strip() or "127.0.0.1"
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    else:
        entered = input(f"Server port [{DEFAULT_PORT}]: ").strip()
        port = int(entered) if entered else DEFAULT_PORT
    return ip, port


def connect_to_server(ip, port):
    """Create a TCP socket and connect. Exits with a clear message on failure."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((ip, port))
    except OSError as err:
        print(f"[ERROR]: Could not connect to {ip}:{port} ({err})")
        sys.exit(1)
    return sock


def main():
    print(f"Chat Client  |  {STUDENT_INFO}")
    try:
        ip, port = get_server_address()
    except ValueError:
        print("[ERROR]: Port must be a number.")
        return
    sock = connect_to_server(ip, port)
    print(f"Connected to {ip}:{port}\n")

    # separate thread receives, so incoming messages never wait for typing
    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    try:
        send_messages(sock)                # the server's "Enter username:" prompt appears first
    except KeyboardInterrupt:
        print("\n[Closing connection]")     # forced close: server will tell others we left
    finally:
        try:
            threading.Event().wait(0.3)    # give the server's "Goodbye!" time to print
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()

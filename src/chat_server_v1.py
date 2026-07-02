import socket
import threading

import asyncio
import re

HOST = "192.0.0.3"
PORT = 8000

clients = []
clients_info = {}
# SERVER_PASSWORD = "SuperSanders123"

def broadcast(message, sender_conn):
    """ Sends message to all clients except sender """
    for client in clients[:]:
        try:
            if client != sender_conn:
                client.sendall(message)
        except OSError:
            clients.remove(client)

def send_pm(message, sender_conn, receiver_name):
    """Send a private message to a specific user."""
    
    # Find the receiver's socket
    receiver = next(
        (conn for conn, name in clients_info.items()
         if name == receiver_name),
        None
    )

    if receiver is None:
        sender_conn.sendall(b"User not found.\n")
        return

    if receiver == sender_conn:
        sender_conn.sendall(b"You can't send a private message to yourself.\n")
        return

    formatted = (
        f"[PM] {clients_info[sender_conn]}: {message}\n"
    ).encode()

    try:
        receiver.sendall(formatted)

        # Optional: Let the sender know it was sent
        sender_conn.sendall(
            f"[PM to {receiver_name}] {message}\n".encode()
        )
        
    except OSError:
        sender_conn.sendall(
            b"Failed to send private message.\n"
        )

def get_username(conn) -> str:
    """Get the username of a client"""  
    while True:
        conn.sendall("Enter a username: ".encode())
        
        data = conn.recv(1024)
        if not data:
            continue
        
        username = data.decode().strip()
        
        if username in clients_info.values():
            conn.sendall(b"Username already taken.\n")
            continue
        
        if re.fullmatch(r"^[a-zA-Z0-9]{2,8}$", username):
            return username
        else:
            conn.sendall(f"{username} is not a valid username".encode())
            continue
        
def greet_user(conn, username):
    """Greet the user with the appropriate message based on their username"""       
    conn.sendall(f"Welcome to the chat {username}!\n".encode())
    broadcast(f"{username} joined\n".encode(), conn)

def user_farewell(conn, username):
    """Execute the user farewell operations"""
    print(f"[DISCONNECTED] {username}")
        
    broadcast(f"{username} left\n".encode(), conn)
    
    if conn in clients:
        clients.remove(conn)
    
    if conn in clients_info:
        del clients_info[conn]
        
    try:
        conn.close()
    except:
        pass 
       
def run_msg_cmd(conn, message):
    """Run the operations associated with the /msg command"""
    message_parts = message.split(maxsplit=2)
    
    if len(message_parts) != 3:
        conn.sendall(b"Usage: /msg <username> <message>\n")
        return
    
    recipient = message_parts[1]
    private_message = message_parts[2]
    send_pm(private_message, conn, recipient)
    
def run_list_cmd(conn):
    """Run the operations associated with the /list command""" 
    message = "Online users:\n"
    
    for user in clients_info.values():
        message += user + "\n"
        
    conn.sendall(message.encode())
    
def run_whoami_cmd(conn, username):
    """Run the operations associated with the /whoami command"""
    message = f"You are {username}\n"
    conn.sendall(message.encode())
    
def handle_client(conn, addr):    
    try:
        print(f"[NEW CONNECTION] {addr}")
        
        clients.append(conn)

        username = get_username(conn)
        clients_info[conn] = username
        
        greet_user(conn, username)
        
        while True:
            data = conn.recv(1024)
            if not data:
                break

            message = data.decode()
            
            print(f"{username}: {message}")
            
            if message.startswith("/msg"):
                run_msg_cmd(conn, message)
            elif message.startswith("/list"):
                run_list_cmd(conn)
            elif message.startswith("/whoami"):
                run_whoami_cmd(conn, username)
            elif message.startswith("/quit"):
                return
            elif message.startswith("/help"):
                # TODO
                pass
            else:
                formatted = f"{username}: {message}".encode()
                broadcast(formatted, conn)
            
    except (OSError, ConnectionResetError):
        pass
    finally:
        user_farewell(conn, username)
        
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print(f"Chat server running on {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()
        
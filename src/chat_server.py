import asyncio
import re
from client import Client

HOST = "192.0.0.2"
PORT = 8000

clients: list[Client] = []

lock = asyncio.Lock()

async def broadcast(message, username):
    """ Sends message to all clients except sender """
    
    dead_clients = []
    
    for client in clients.copy():
        if client.username != username:
            try:
                client.writer.write(message)
                await client.writer.drain()
            except ConnectionError:
                dead_clients.append(client)
    
    async with lock:
        for client in dead_clients:
            clients.remove(client)
        
async def get_username(reader, writer) -> str:
    """Get the username of a client"""
    
    while True:
        writer.write(b"Enter a username: ")
        await writer.drain()
        
        data = await reader.readline()
        if not data:
            continue
        
        username = data.decode().strip()
        
        for client in clients:
            if client.username == username:
                writer.write(b"Username already taken.\n")
                await writer.drain()
                continue
        
        if re.fullmatch(r"^[a-zA-Z0-9]{2,12}$", username):
            return username
        else:
            writer.write(f"{username} is not a valid username\n".encode())
            await writer.drain()
            continue
  
async def greet_user(writer, username):
    """Greet the user with the appropriate message based on their username""" 
    
    writer.write(f"Welcome to the chat {username}!\n".encode())
    await broadcast(f"{username} joined\n".encode(), username)

async def user_farewell(writer, username, addr):
    """Execute the user farewell operations"""
    
    print(f"Disconnected: {username} @ {addr}")
    await broadcast(f"{username} left\n".encode(), username)
        
    await remove_user_from_client_ls(username)
    writer.close()
    await writer.wait_closed()

async def send_pm(message, writer, sender_name, receiver_name):
    """Send a private message to a specific user"""
    
    if sender_name == receiver_name:
        writer.write(b"You can't send a private message to yourself.\n")
        await writer.drain()
        return
    
    receiver = next(
        (client for client in clients if client.name == receiver_name),
        None)
    
    if not receiver:
        writer.write(b"User not found\n")
        await writer.drain()
        return
    
    formatted = f"[PM] {sender_name}: {message}\n".encode()
    
    try:
        receiver.writer.write(formatted)
        await receiver.writer.drain()
        
        writer.write(f"[PM to {receiver_name}] {message}\n".encode())
        await writer.drain()
        
    except OSError:
        writer.write(b"Failed to send private message.\n")
        await writer.drain()
       
async def run_msg_cmd(message, writer, sender):
    """Run the operations associated with the /msg command"""
    
    message_parts = message.split(maxsplit=2)
    
    if len(message_parts) != 3:
        writer.write(b"Usage: /msg <username> <message>\n")
        await writer.drain()
        return
    
    recipient = message_parts[1]
    private_message = message_parts[2]
    await send_pm(private_message, writer, sender, recipient)
    
async def remove_user_from_client_ls(username):
    """ Remove a user from the client list"""  
    for client in clients:
        if client.username == username:
            clients.remove(client)
  
async def handle_client(reader, writer):
    """ Handle a new client 

    Args:
        reader: the reader of the new client
        writer: the writer of the new client
    """
       
    try:
        addr = writer.get_extra_info("peername")   
        print(f"Connected: {addr}")
        
        username = await get_username(reader, writer)
        
        clients.append(Client(reader, writer, username))
        
        await greet_user(writer, username)
        
        while True:
            data = await reader.readline()
            if not data:
                break
            
            message = data.decode().strip()
            print(f"{username}: {message}")
            
            if message.startswith("/msg"):
                await run_msg_cmd(message, writer, username)
            formatted = f"{username}: {message}\n".encode()
            await broadcast(formatted, username)
            
    except Exception as e:
        print(e)
        
    finally:
        await user_farewell(writer, username, addr)
        
async def run_server():
    """ Runs a server on the Host using the port """
    server = await asyncio.start_server(
        handle_client,
        HOST,
        PORT
    )
    
    print(f"Chat server running on {HOST}:{PORT}")
    
    async with server:
        await server.serve_forever()

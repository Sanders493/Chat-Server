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
        
async def get_username(reader, writer):
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
            writer.write(f"{username} is not a valid username".encode())
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

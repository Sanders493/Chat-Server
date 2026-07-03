import asyncio
import re
from client import Client

HOST = "192.0.0.3"
PORT = 8000

clients: list[Client] = []

lock = asyncio.Lock()

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
            print(message)
            
    except Exception as e:
        print(e)
        
    finally:
        print(f"Disconnected: {addr}")
        writer.close()
        await writer.wait_closed()
        

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

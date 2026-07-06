import asyncio
import re
from client import Client
import json
import bcrypt # type: ignore

with open("config-files/config.json") as f:
    config = json.load(f)

HOST = config.host
PORT = config.port
SERVER_PASSWORD = config.server_password

clients: dict[dict] = {}

with open("data-files/users.json", "r") as data_file:
    clients = json.load(data_file)

connected_clients = []

# TODO finish user data logic


lock = asyncio.Lock()

async def broadcast(message, username):
    """ Sends message to all clients except sender """
    
    dead_clients = []
    
    for client in connected_clients.copy():
        if client.username != username:
            try:
                client.writer.write(message)
                await client.writer.drain()
            except ConnectionError:
                dead_clients.append(client)
    
    async with lock:
        for client in dead_clients:
            connected_clients.remove(client)
        
async def get_username(reader, writer, is_signup: bool=False) -> str:
    """Get the username of a client"""
    
    while True:
        await send_message_to_user(writer, "Enter a username: " if is_signup else "Enter username: ")
        
        data = await reader.readline()
        if not data:
            raise ConnectionError("Client disconnected")
        
        username = data.decode().strip()
        
        if is_signup:
            if not username:
                await send_message_to_user(writer, "Username cannot be empty")
                continue
            
            if not re.fullmatch(r"^[a-zA-Z0-9]{2,20}$", username):
                await send_message_to_user(writer, "Username must be 2-20 letters or digits.")
                continue
            
            if any(client.username == username for client in connected_clients):
                await send_message_to_user(writer, "Username already taken.")
                continue

        return username

async def get_password(reader, writer, is_signup: bool = False) -> str:
    """Get the password of a client"""
    
    while True:
        await send_message_to_user(writer, "Enter a password: " if is_signup else "Enter password: ")
        
        data = await reader.readline()
        if not data:
            raise ConnectionError("Client disconnected")
        
        password = data.decode().strip()
        
        if not password:
            await send_message_to_user(writer, "You didn't enter anything")
            continue
        
        if is_signup:
            if not await validate_password(writer, password):
                continue
            
            await send_message_to_user(writer, "Confirm password: ")
            
            data = await reader.readline()
            if not data:
                raise ConnectionError("Client disconnected")
            
            password_input2 = data.decode().strip()
             
            if password != password_input2:
                await send_message_to_user(writer, "Passwords do not match.")
                continue
            
        return password

async def validate_password(writer, password: str) -> bool:
    """Run validation checks on the given password"""
    
    if len(password) < 8:
        await send_message_to_user(writer, "Password must contain at least 8 characters")
        return False
    
    if len(password) > 128:
        await send_message_to_user(writer, "Password cannot exceed 128 characters.")
        return False
    
    if not re.search(r"[A-Z]", password):
        await send_message_to_user(writer, "Password must contain at least one uppercase letter")
        return False
    
    if not re.search(r"[a-z]", password):
        await send_message_to_user(writer, "Password must contain at least one lowercase letter")
        return False
    
    if not re.search(r"\d", password):
        await send_message_to_user(writer, "Password must contain at least one digit")
        return False
    
    if not re.search(r"[!#$%*+]", password):
        await send_message_to_user(writer, "Password must contain at least one of these special characters [!#$%*+]")    
        return False
    
    return True
    
async def hash_password(password: str) -> bytes:
    """ Hash the password """
    
    password_hashed = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt())
    
    print(password_hashed)
    return password_hashed
        
async def greet_user(writer, username):
    """Greet the user with the appropriate message based on their username""" 
    
    await send_message_to_user(writer, f"Welcome to the chat {username}!")
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
        await send_message_to_user(writer, "You can't send a private message to yourself.")
        return
    
    receiver = next(
        (client for client in connected_clients if client.username == receiver_name),
        None)
    
    if not receiver:
        await send_message_to_user(writer, "User not found")
        return
    
    formatted = f"[PM] {sender_name}: {message}\n".encode()
    
    try:
        await send_message_to_user(receiver.writer, formatted)
        
        await send_message_to_user(writer, f"[PM to {receiver_name}] {message}")
        
    except OSError:
        await send_message_to_user(writer, "Failed to send private message.")
       
async def run_msg_cmd(message, writer, sender):
    """Run the operations associated with the /msg command"""
    
    message_parts = message.split(maxsplit=2)
    
    if len(message_parts) != 3:
        await send_message_to_user(writer, "Usage: /msg <username> <message>")
        return
    
    recipient = message_parts[1]
    private_message = message_parts[2]
    await send_pm(private_message, writer, sender, recipient)

async def run_list_cmd(writer):
    """Run the operations associated with the /list command"""
    
    message = "Online users:\n"
    
    for client in connected_clients:
        message += client.username + "\n"

    await send_message_to_user(writer, message)
 
async def run_whoami_cmd(writer, username):
    """Run the operations associated with the /whoami command"""
    
    message = f"You are {username}\n"

    await send_message_to_user(writer, message)

async def run_help_cmd(writer):
    """Run the operations associated with the help command"""
    help_text = (
        "\n"
        "================ Chat Commands ================\n\n"
        "/help\n"
        "    Show this help menu.\n\n"
        "/list\n"
        "    Display all users currently connected.\n\n"
        "/users\n"
        "    Same as /list command\n\n"
        "/whoami\n"
        "    Display your current username.\n\n"
        "/msg <username> <message>\n"
        "    Send a private message to another user.\n\n"
        "    Example:\n"
        "        /msg Alice Hello!\n\n"
        "/quit\n"
        "    Disconnect from the chat server.\n\n"
        "===============================================\n"
    )

    writer.write(help_text.encode())
    await writer.drain()

async def send_message_to_user(writer, message: str):
    """Send an message to the user"""
    writer.write(f"{message}\n".encode())
    await writer.drain()
    
async def ask_for_server_password(reader, writer) -> bool:
    """Ask the user for the server password before they can join."""

    MAX_ATTEMPTS = 5
    attempt = 0
    
    for _ in range(MAX_ATTEMPTS):
        await send_message_to_user(writer, "Server password: ")

        data = await reader.readline()
        if not data:
            raise ConnectionError("Client disconnected")

        password = data.decode().strip()

        if password == SERVER_PASSWORD:
            return True

        await send_message_to_user(writer, f"ACCESS DENIED: Incorrect password ({attempt + 1}/{MAX_ATTEMPTS})")
        attempt += 1

    await send_message_to_user(writer, "Too many failed attempts.")

    return False
    
async def signup_or_login(reader, writer) -> tuple[bool, str]:
    """Run the operations associated with asking the user if he/she's signing up or login in"""
    
    while True:
        message = (
            "1: Log in\n"
            "2: Sign up\n"
        ).encode()
        
        writer.write(message)
        await writer.drain()
        
        user_input = await reader.readline()
        
        if not user_input:
            raise ConnectionError("Client disconnected")
        
        user_response = user_input.decode().strip()
        
        if user_response == "2":
            response = await run_user_signup(reader, writer)
        elif user_response == "1":
            response = await run_user_login(reader, writer)
        
        return response # (access_granted = false, placeholder because user couldn't signup)
        
async def run_user_signup(reader, writer) -> tuple:
    """Run the operations associated with the user sign up process"""     
    
    access_granted = await ask_for_server_password(reader, writer)
    
    if access_granted:
        username = await get_username(reader, writer, is_signup=True)
        password = await get_password(reader, writer, is_signup=True)
        
        hashed_password = await hash_password(password)
        async with lock:
            connected_clients.append(Client(reader, writer, username, hashed_password))
            
        return (True, username)
    
    return (False, "Unknown")

async def run_user_login(reader, writer) -> tuple[bool, str]:
    """ Run the operations associated with the user logging in process"""
    
    access_granted = False
    username = await get_username(reader, writer)
    
    client = next(
        (client for client in connected_clients if username == client.username),
        None)
    
    if not client:
        send_message_to_user(writer, message="The user was not found")
        return (access_granted, "Unknown")
    
    entered_password = await get_password(reader, writer)
    
    access_granted = await check_password_correct(reader, writer,entered_password, client)
    
    return (access_granted, username)
    
async def check_password_correct(reader, writer,entered_password: str, user: Client) -> bool:
    """Check if the password entered is the correct password for the current user"""
    
    MAX_ATTEMPTS = 5
    attempt = 0
    
    for _ in range(MAX_ATTEMPTS): 
        await send_message_to_user(writer, "Enter password: ")

        data = await reader.readline()
        if not data:
            raise ConnectionError("Client disconnected")

        entered_password = data.decode().strip()

        if bcrypt.checkpw(
        entered_password.encode(),
        user.password):
            return True

        await send_message_to_user(writer, f"Incorrect password ({attempt + 1}/{MAX_ATTEMPTS})")
        attempt += 1
        
    await send_message_to_user(writer, "Too many failed attempts")

    return False
    
async def remove_user_from_client_ls(username):
    """ Remove a user from the client list"""  
    for client in connected_clients:
        if client.username == username:
            connected_clients.remove(client)
  
async def handle_client(reader, writer):
    """ Handle a new client 

    Args:
        reader: the reader of the new client
        writer: the writer of the new client
    """
       
    try:
        addr = writer.get_extra_info("peername")   
        print(f"Connected: {addr}")
        
        access_granted = False
        
        access_granted, username = await signup_or_login(reader, writer)
        
        if not access_granted:
            return
        
        await greet_user(writer, username)
        
        while True:
            data = await reader.readline()
            if not data:
                break
            
            message = data.decode().strip()
            print(f"{username}: {message}")
            
            if message.startswith("/msg"):
                await run_msg_cmd(message, writer, username)
            elif message.startswith("/list") or message.startswith("/users"):
                await run_list_cmd(writer)
            elif message.startswith("/whoami"):
                await run_whoami_cmd(writer, username)
            elif message.startswith("/help"):
                await run_help_cmd(writer)
            elif message.startswith("/quit"):
                return
            else:
                formatted = f"{username}: {message}\n".encode()
                await broadcast(formatted, username)
            
    except Exception as e:
        print(e)
        
    finally:
        if access_granted:
            await user_farewell(writer, username, addr)
        else:
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

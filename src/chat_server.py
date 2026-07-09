import asyncio
import re
from client import Client
from chat_room import ChatRoom
from asyncio import StreamReader, StreamWriter
import json
import bcrypt # type:ignore

with open("config-files/config.json", "r") as f:
    config = json.load(f)

HOST = config["host"]
PORT = config["port"]
SERVER_PASSWORD = config["server_password"]
USERS_DATA_FILE_PATH = config["users_data_file_path"]

clients: dict[dict] = {}
connected_clients: list[Client] = []
rooms: dict[str, ChatRoom] = {
    "General": ChatRoom("general"),
    "Programming": ChatRoom("programming"),
    "Sports": ChatRoom("sports"),
    "Music": ChatRoom("music")
}

lock = asyncio.Lock()

def load_users(data_file_path: str):
    """Load the clients dictionary with data from the json file

    Args:
        data_file_path (str): the path of the file that contains the users' data
    """
    global clients
    try:
        with open(data_file_path, "r") as data_file:
            clients = json.load(data_file)
    except FileNotFoundError:
        clients = {}
    except json.JSONDecodeError:
        clients = {}
    
def save_users(data_file_path: str):
    """Save the data of the clients dictionary to the json file

    Args:
        data_file_path (str): the path of the file that contains the users' data
    """
    try:
        with open(data_file_path, "w") as data_file:
            json.dump(clients, data_file, indent=4)
    except FileNotFoundError:
        print(f"{data_file_path} doesn't exist")
    
async def broadcast(message: str, username: str):
    """Sends message to all clients except sender

    Args:
        message (str): the message to be sent to all users
        username (str): the username of the message sender
    """
    
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
        
async def get_username(reader: StreamReader, writer: StreamWriter, is_signup: bool=False) -> str:
    """Get the username of a client

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client
        is_signup (bool, optional): whether or not the method is used for user's sign up. Defaults to False.

    Raises:
        ConnectionError: is raised whenever the user disconnects

    Returns:
        str: the username entered by the client
    """
    
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
            
            if any(client == username for client in clients):
                await send_message_to_user(writer, "Username already taken.")
                continue

        return username

async def get_password(reader: StreamReader, writer: StreamWriter, is_signup: bool = False) -> str:
    """Get the password of a client

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client
        is_signup (bool, optional): whether or not the method is used for user's sign up. Defaults to False.

    Raises:
        ConnectionError: is raised whenever the user disconnects
        ConnectionError: is raised whenever the user disconnects

    Returns:
        str: the password entered by the client
    """
    
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

async def validate_password(writer: StreamWriter, password: str) -> bool:
    """Run validation checks on the given password

    Args:
        writer (StreamWriter): the stream writer of the client
        password (str): the password being validated

    Returns:
        bool: whether or not the password was validated
    """
    
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
    """Hash the password

    Args:
        password (str): the password to hash

    Returns:
        bytes: the hashed password
    """
    
    password_hashed = bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt())
    
    return password_hashed
        
async def greet_user(writer: StreamWriter, username: str):
    """Greet the user with the appropriate message based on their username

    Args:
        writer (StreamWriter): the stream writer of the client
        username (str): the client's username
    """
    
    await send_message_to_user(writer, f"Welcome to the chat {username}!")
    await broadcast(f"{username} joined\n".encode(), username)

async def user_farewell(writer: StreamWriter, username: str, addr: str):
    """Execute the user farewell operations

    Args:
        writer (StreamWriter): the stream writer of the client
        username (str): the client's username
        addr (str): the client's ip address
    """
    
    print(f"Disconnected: {username} @ {addr}")
    await broadcast(f"{username} left\n".encode(), username)
        
    await remove_user_from_client_ls(username)
    writer.close()
    await writer.wait_closed()

async def send_pm(message: str, writer: StreamWriter, sender_name: str, receiver_name: str):
    """Send a private message to a specific user

    Args:
        message (str): the message being sent
        writer (StreamWriter): Send a private message to a specific user
        sender_name (str): the sender's username
        receiver_name (str): the receiver's username
    """
    
    if sender_name == receiver_name:
        await send_message_to_user(writer, "You can't send a private message to yourself.")
        return
    
    receiver = next(
        (client for client in connected_clients if client.username == receiver_name),
        None)
    
    if not receiver:
        await send_message_to_user(writer, "User not found")
        return
    
    formatted = f"[PM] {sender_name}: {message}\n"
    
    try:
        await send_message_to_user(receiver.writer, formatted)
        
        await send_message_to_user(writer, f"[PM to {receiver_name}] {message}")
        
    except OSError:
        await send_message_to_user(writer, "Failed to send private message.")
       
async def run_msg_cmd(message: str, writer: StreamWriter, sender: str):
    """Run the operations associated with the /msg command

    Args:
        message (str): the message being sent
        writer (StreamWriter): the stream writer of the client
        sender (str): the sender's username
    """
    
    message_parts = message.split(maxsplit=2)
    
    if len(message_parts) != 3:
        await send_message_to_user(writer, "Usage: /msg <username> <message>")
        return
    
    recipient = message_parts[1]
    private_message = message_parts[2]
    await send_pm(private_message, writer, sender, recipient)

async def run_list_cmd(writer: StreamWriter):
    """Run the operations associated with the /list command

    Args:
        writer (StreamWriter): the stream writer of the client
    """
    
    message = "Online users:\n"
    
    for client in connected_clients:
        message += client.username + "\n"

    await send_message_to_user(writer, message)
 
async def run_whoami_cmd(writer: StreamWriter, username: str):
    """Run the operations associated with the /whoami command

    Args:
        writer (StreamWriter): the stream writer of the client
        username (str): the client's username
    """
    
    message = f"You are {username}\n"

    await send_message_to_user(writer, message)

async def run_help_cmd(writer: StreamWriter):
    """Run the operations associated with the help command

    Args:
        writer (StreamWriter): the stream writer of the client
    """
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

async def send_message_to_user(writer: StreamWriter, message: str):
    """Send an message to the user

    Args:
        writer (StreamWriter): the stream writer of the client
        message (str): the message being sent
    """
    writer.write(f"{message}\n".encode())
    await writer.drain()
    
async def ask_for_server_password(reader: StreamReader, writer: StreamWriter) -> bool:
    """Ask the user for the server password before they can join.

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client

    Raises:
        ConnectionError: is raised whenever the user disconnects

    Returns:
        bool: whether or not the client is allowed to access the server
    """

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
    
async def signup_or_login(reader: StreamReader, writer: StreamWriter) -> tuple[bool, str]:
    """Run the operations associated with asking the user if he/she's signing up or login in

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client

    Raises:
        ConnectionError: is raised whenever the user disconnects

    Returns:
        tuple[bool, str]: a tuple contain the whether or not the user can access the server and the user's username
    """
    
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
        
async def run_user_signup(reader: StreamReader, writer: StreamWriter) -> tuple:
    """Run the operations associated with the user sign up process

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client

    Returns:
        tuple: a tuple contain the whether or not the user can access the server and the user's username
    """
    
    access_granted = await ask_for_server_password(reader, writer)
    
    if access_granted:
        username = await get_username(reader, writer, is_signup=True)
        password = await get_password(reader, writer, is_signup=True)
        
        hashed_password = await hash_password(password)
        async with lock:
            connected_clients.append(Client(reader, writer, username))
            clients[username] = {
                "password": hashed_password.decode()
                }
            
        save_users(USERS_DATA_FILE_PATH)
        load_users(USERS_DATA_FILE_PATH)
        return (True, username)
    
    return (False, "Unknown")

async def run_user_login(reader: StreamReader, writer: StreamWriter) -> tuple[bool, str]:
    """Run the operations associated with the user logging in process

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client

    Returns:
        tuple[bool, str]: a tuple contain the whether or not the user can access the server and the user's username
    """
    
    access_granted = False
    username = await get_username(reader, writer)
    
    client = clients.get(username, None)
    
    if not client:
        await send_message_to_user(writer, message="The user was not found")
        return (access_granted, "Unknown")
     
    access_granted = await check_password_correct(reader, writer, client)
    
    if access_granted:
        connected_clients.append(Client(reader, writer, username))
    return (access_granted, username)
    
async def check_password_correct(reader: StreamReader, writer: StreamWriter, user: dict) -> bool:
    """Check if the password entered is the correct password for the current user

    Args:
        reader (StreamReader): the stream reader of the client
        writer (StreamWriter): the stream writer of the client
        user (dict): the client's dictionary  

    Returns:
        bool: whether or not the password entered by the user is correct
    """
    
    MAX_ATTEMPTS = 5
    attempt = 0
    
    for _ in range(MAX_ATTEMPTS): 
        entered_password = await get_password(reader, writer)
        stored_hash = user["password"].encode()
        if bcrypt.checkpw(
        entered_password.encode(),
        stored_hash
        ):
            return True

        await send_message_to_user(writer, f"Incorrect password ({attempt + 1}/{MAX_ATTEMPTS})")
        attempt += 1
        
    await send_message_to_user(writer, "Too many failed attempts")

    return False
    
async def remove_user_from_client_ls(username: str):
    """Remove a user from the client list

    Args:
        username (str): the client's username
    """
    for client in connected_clients:
        if client.username == username:
            connected_clients.remove(client)

async def process_command(writer: StreamWriter, message: str, username: str) -> int:
    """Process the user message

    Args:
        writer (StreamWriter): the stream writer of the client
        message (str): the message being sent
        username (str): the client's username

    Returns:
        int: code describing the result of the command
    """

    if message.startswith("/msg"):
        await run_msg_cmd(message, writer, username)
    elif message.startswith("/list") or message.startswith("/users"):
        await run_list_cmd(writer)
    elif message.startswith("/whoami"):
        await run_whoami_cmd(writer, username)
    elif message.startswith("/join"):
        pass
    elif message.startswith("/leave"):
        pass
    elif message.startswith("/help"):
        await run_help_cmd(writer)
    elif message.startswith("/quit"):
        return 1 # code for user wants to quit
    else:
        formatted = f"{username}: {message}\n".encode()
        await broadcast(formatted, username)
    
    return 0 # code for every other commands
        
async def handle_client(reader: StreamReader, writer: StreamWriter):
    """ Handle a new client 

    Args:
        reader (StreamReader): the reader of the new client
        writer (StreamWriter): the writer of the new client
    """
       
    try:
        addr = writer.get_extra_info("peername")   
        print(f"Connected: {addr}")
        print(type(reader))
        print(type(writer))
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
            command_result = await process_command(writer, message, username)
            
            if command_result == 1:
                return
            
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
    load_users(USERS_DATA_FILE_PATH)
    
    server = await asyncio.start_server(
        handle_client,
        HOST,
        PORT
    )
    
    print(f"Chat server running on {HOST}:{PORT}")
    
    async with server:
        await server.serve_forever()
    
    save_users(USERS_DATA_FILE_PATH)
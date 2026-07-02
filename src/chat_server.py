import asyncio
import re
import client

HOST = "192.0.0.3"
PORT = 8000

lock = asyncio.Lock()

async def handle_client(reader, writer):
    try:
        pass
    except:
        pass
        

async def run_server():
    server = await asyncio.start_server(
        handle_client,
        HOST,
        PORT
    )
    
    print(f"Chat server running on {HOST}:{PORT}")

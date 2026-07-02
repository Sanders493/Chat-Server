import asyncio
import re
import client

HOST = "192.0.0.3"
PORT = 8000

clients = []

lock = asyncio.Lock()

async def handle_client(reader, writer):
    """ Handle a new client 

    Args:
        reader: the reader of the new client
        writer: the writer of the new client
    """
    
    addr = writer.get_extra_info("peername")   
    print(f"Connected: {addr}")
    
    try:
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

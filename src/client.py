from chat_room import ChatRoom
from asyncio import StreamReader, StreamWriter
class Client:
    """ Represents the attributes and behavior of a server client"""
    
    def __init__(self, reader: StreamReader, writer: StreamWriter, username: str, room: ChatRoom = None):
        """ Create a client object

        Args:
            reader (StreamReader): the stream reader of the client
            writer (StreamWriter): the stream writer of the client
            username (str): the client's username
            room (ChatRoom, optional): the chatroom that the client is currently in. Defaults to None.
        """
        self.reader = reader
        self.writer = writer
        self.username: str = username
        self.room = room
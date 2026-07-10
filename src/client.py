from __future__ import annotations
from typing import TYPE_CHECKING
from asyncio import StreamReader, StreamWriter

if TYPE_CHECKING:
    from chat_room import ChatRoom
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
        self.reader: StreamReader = reader
        self.writer: StreamWriter = writer
        self.username: str = username
        self.room: ChatRoom = room
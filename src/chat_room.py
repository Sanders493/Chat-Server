from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import Client
class ChatRoom:
    """Represents the attributes and behavior of a chat room"""
    
    def __init__(self, name: str):
        """ Create a chat room object

        Args:
            name (str): the name of the chat room
        """
        self.name = name
        self.members: set[Client] = set()
        
    def add_member(self, new_member: Client):
        """Add a member to the chat room

        Args:
            new_member (Client): the member being added to the chat room
        """
        self.members.add(new_member)
    
    def remove_member(self, member: Client):
        """Remove a member from the chat room

        Args:
            member (Client): the member to be removed
        """
        if member in self.members:
            self.members.remove(member)
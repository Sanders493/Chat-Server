class ChatRoom:
    """Represents the attributes and behavior of a chat room"""
    
    def __init__(self, name: str):
        """ Create a chat room object

        Args:
            name (str): the name of the chat room
        """
        self.name = name
        self.members = set()
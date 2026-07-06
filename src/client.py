class Client:
    """ Represents the attributes and behavior of a server client"""
    
    def __init__(self, reader, writer, username):
        self.reader = reader
        self.writer = writer
        self.username: str = username
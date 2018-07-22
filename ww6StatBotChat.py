from enum import IntEnum


class ChatType(IntEnum):
    CHAT = 0
    SQUAD = 1
    BAND = 2


from_str = {'chat': ChatType.CHAT, 'squad': ChatType.SQUAD, 'band': ChatType.BAND}
to_str = {ChatType.CHAT: 'chat', ChatType.SQUAD: 'squad', ChatType.BAND: 'band'}


class Chat:
    def __init__(self):
        self.chat_id = 0
        self.members = set()
        self.masters = set()
        self.title = ""  # full name of chat
        self.name = ""  # short name of chat user as a key
        self.chat_type = ChatType.CHAT

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.name == str(other)

    def __copy__(self):
        res = Chat()
        res.chat_id, res.title, res.name = self.chat_id, self.title, self.name
        res.members = self.members.copy()
        res.masters = self.masters.copy()
        return res

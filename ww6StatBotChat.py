from ww6StatBotPlayer import Player


class Chat:
    def __init__(self):
        self.chat_id = 0
        self.members = set()
        self.title = ""  # full name of chat
        self.name = ""  # short name of chat user as a key

    def __hash__(self):
        hash(self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.name == str(other)

    def __copy__(self):
        res = Chat()
        res.chat_id, res.title, res.name = self.chat_id, self.title, self.name
        res.members = self.members.copy()
        return res


class Squad(Chat):
    def __init__(self):
        super().__init__()
        self.masters = set()

    def __copy__(self):
        res = Chat()
        res.chat_id, res.title, res.name = self.chat_id, self.title, self.name
        res.members = self.members.copy()
        res.masters = self.masters.copy()

import re
import warnings

from ww6StatBotChat import Chat, ChatType
from ww6StatBotPlayer import Player
from ww6StatBotSQL import SQLManager

__all__ = [
    'DataBox',
]


class DataBox:
    def __init__(self, sql_manager: SQLManager):
        self.sql_manager = sql_manager
        self._players = self.sql_manager.get_all_players()  # Players
        self._players_by_username = {pl.username.lower(): pl for pl in self._players.values()}  # Players
        self._blacklist = set(self.sql_manager.get_blacklist())  # user ids
        self._admins = set(self.sql_manager.get_admins())  # user ids
        self._chats = {}  # Chat all, including bands and squads
        self._squads = {}  # Chat
        self._bands = {}  # Chat
        self._chats_by_id = {}

        self._names = {'none', 'all'}

        chats = self.sql_manager.get_all_chats()
        masters = self.sql_manager.get_all_masters_uids()
        members = self.sql_manager.get_all_chat_members_uids()
        for chat in chats:
            self._chats[chat.name] = chat
            self._chats_by_id[chat.chat_id] = chat
            mem = members.get(chat.name)
            if mem:
                for uid in mem:
                    pl = self._players.get(uid)
                    chat.members.add(pl)
                    if chat.chat_type == Chat.ChatType.SQUAD:
                        pl.squad = chat
            mas = masters.get(chat.name)
            if mas:
                for uid in mas:
                    chat.masters.add(self._players.get(uid))

            self._names.add(chat.name)
            if chat.chat_type == Chat.ChatType.SQUAD:
                self._squads[chat.name] = chat
            elif chat.chat_type == Chat.ChatType.BAND:
                self._bands[chat.name] = chat

    def add_player(self, uid, username, nic) -> Player:
        '''
        Adds player to DB and cache
        '''
        pl = Player()
        pl.uid = uid
        pl.username = username
        pl.nic = nic
        self._players[uid] = pl
        self._players_by_username[username.lower()] = pl
        self.sql_manager.add_user(pl)
        return pl

    def del_player(self, player):
        '''
        Removes player from everywhere.
        Does not checks that given player exist
        '''
        self.sql_manager.del_user(player)
        del (self._players[player.uid])
        del (self._players_by_username[player.username.lower()])
        for chat in self._chats:
            if player in chat.masters:
                chat.masters.remove(player)
            if player in chat.members:
                chat.members.remove(player)

    def player(self, uid: int) -> Player:
        warnings.warn(
            "player is deprecated, use get_player_by_uid instead",
            PendingDeprecationWarning
        )
        return self.get_player_by_uid(uid)

    def get_player_by_uid(self, uid: int) -> Player:
        '''
        Returns Player with given telegram user id if known or None
        '''
        return self._players.get(uid)

    def player_by_username(self, username: str) -> Player:
        warnings.warn(
            "player_by_username is deprecated, use get_player_by_username instead",
            PendingDeprecationWarning
        )
        return self.get_player_by_username(username)

    def get_player_by_username(self, username: str) -> Player:
        '''
        Returns Player with given telegram username if known or None
        '''
        return self._players_by_username.get(username.strip('@,-._').lower())

    def all_players(self) -> set:
        return set(self._players.values())

    def all_player_usernames(self) -> set:
        '''
        Returns all players names *in lower case*
        '''
        return set(self._players_by_username.keys())
    
    def add_blacklist(self, player: Player):
        self.sql_manager.add_blacklist(player)
        self._blacklist.add(player.uid)

    def uid_in_blacklist(self, uid: int) -> bool:
        return uid in self._blacklist
    
    def add_admin(self, player: Player):
        self.sql_manager.add_admin(player)
        self._admins.add(player.uid)
    
    def del_admin(self, player: Player):
        self.sql_manager.del_admin(player)
        try:
            self._admins.remove(player.uid)
        except KeyError:
            pass

    def uid_is_admin(self, uid: int) -> bool:
        return uid in self._admins

    def player_is_admin(self, player: Player) -> bool:
        return player.uid in self._admins

    def player_has_rights(self, player: Player, squad: Chat=None) -> bool:
        return self.player_is_admin(player) or (squad and player in squad.masters)

    def players_by_username(self, _str: str, offset=0, parse_all=True):
        """
        if parse_all=True returns set of players and list of unknown usernames
        else - set of players and the rest of the string
        """
        res = set()
        negative = set()
        name = re.compile('@?(\S+)\s*')
        i = left = 0
        m = name.match(_str[left:])
        while m:
            username = m.group(1).lower()
            if i >= offset:
                pl = self._players_by_username.get(username)
                if pl:
                    res.add(pl)
                else:
                    if not parse_all:
                        return res, _str[left:]
                    negative.add('@' + username)
            i += 1
            left += len(m.group(0))
            m = name.match(_str[left:])
        return res, negative
    
    def add_chat(self, chat_id: int, name: str, full_name: str, chat_type=ChatType.CHAT):
        chat = Chat()
        chat.chat_id = chat_id
        chat.title = full_name
        chat.name = name
        chat.chat_type = ChatType.CHAT

        self.sql_manager.add_chat(chat)

        self._chats[chat.name] = chat
        self._chats_by_id[chat.chat_id] = chat
        self._names.add(chat.name)

        return chat


    def chats_by_name(self, _str: str, offset=0, parse_all=True, chat_type=ChatType.CHAT):
        """
        if parse_all=True returns set of chats and list of unknown chatnames
        else - set of chats and the rest of the string
        """
        res = set()
        negative = set()
        name = re.compile('(\S+)\s*')
        src = {ChatType.CHAT: self._chats, ChatType.SQUAD: self._squads, ChatType.BAND: self._bands}[
            chat_type]
        i = left = 0
        m = name.match(_str[left:])
        while m:
            chat_name = m.group(1).lower()
            if i >= offset:
                ch = src.get(chat_name)
                if ch:
                    res.add(ch)
                else:
                    if not parse_all:
                        return res, _str[left:]
                    negative.add(chat_name)
            i += 1
            left += len(m.group(0))
            m = name.match(_str[left:])
        return res, negative

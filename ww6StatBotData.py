from ww6StatBotPlayer import Player
import ww6StatBotChat as Chat
from ww6StatBotSQL import SQLManager
import re


class DataBox:
    def __init__(self, sql_manager: SQLManager):
        self.sql_manager = sql_manager
        self._players = self.sql_manager.get_all_players()  # Players
        self._players_by_username = {pl.username: pl for pl in self._players.values()}  # Players
        self._blacklist = set(self.sql_manager.get_blacklist())  # user ids
        self._admins = (self.sql_manager.get_admins())  # user ids
        self._chats = {}  # Chat
        self._squads = {}  # Squad
        self._names = {'none', 'all'}

        chats_and_types = self.sql_manager.get_all_chats()
        masters = self.sql_manager.get_all_masters_uids()
        members = self.sql_manager.get_all_chat_members_uids()
        for chat, chat_type in chats_and_types:
            if chat_type == 'squad':
                sq = Chat.Squad()
                sq.name, sq.chat_id, sq.title = chat.name, chat.chat_id, chat.title
                mem = members.get(chat.name)
                if mem():
                    for uid in mem:
                        sq.members.add(self._players.get(uid))
                mas = masters.get(chat.name)
                if mas:
                    for uid in mas:
                        sq.masters.add(self._players.get(uid))
                self._squads[sq.name] = sq
            else:
                cht = Chat.Chat()
                cht.name, cht.chat_id, cht.title = chat.name, chat.chat_id, chat.title
                mem = members.get(chat.name)
                if mem():
                    for uid in mem:
                        cht.members.add(self._players.get(uid))
                self._chats[cht.name] = cht
            self._names.add(chat.name)

    def add_player(self, uid, username, nic) -> Player:
        pl = Player()
        pl.uid = uid
        pl.username = username
        pl.nic = nic
        self._players[uid] = pl
        self._players_by_username[username.lower()] = pl
        self.sql_manager.add_user(pl)
        return pl

    def player(self, uid):
        return self._players.get(uid)

    def player_by_username(self, username) -> Player:
        return self._players_by_username.get(username.strip('@,-').lower())

    def all_players(self) -> set:
        return set(self._players.values())

    def all_player_usernames(self) -> set:
        return set(self._players_by_username.keys())

    def uid_in_blacklist(self, uid: int) -> bool:
        return uid in self._blacklist

    def uid_is_admin(self, uid: int) -> bool:
        return uid in self._admins

    def player_is_admin(self, player: Player) -> bool:
        return player.uid in self._admins

    def player_has_rights(self, player: Player, squad: Chat.Squad) -> bool:
        return self.player_is_admin(player) or player in squad.masters

    def players_by_username(self, _str: str, offset=0, parse_all=True):
        """
        if parse_all=True returns list of players and list of unknown usernames
        else - list of players and the rest of the string
        """
        res = set()
        negative = set()
        name = re.compile('@?(\S+)\s*')
        i = l = 0
        m = name.match(_str[l:])
        while m:
            username = m.group(1).lower()
            if i >= offset:
                pl = self._players_by_username.get(username)
                if pl:
                    res.add(pl)
                else:
                    if not parse_all:
                        return res, _str[l:]
                    negative.add('@'+username)
            i += 1
            l += len(m.group(0))
            m = name.match(_str[l:])
        return res, negative

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

    def add_player(self, uid, username, nic):
        pl = Player()
        pl.uid = uid
        pl.username = username
        pl.nic = nic
        self._players[uid] = pl
        self._players_by_username[username.lower()] = pl
        self.sql_manager.add_user(pl)

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

    def player_has_rigts(self, player: Player, squad: Chat.Squad) -> bool:  # TODO: update after Squad class
        return self.player_is_admin(player)

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

import sqlite3 as sql

import ww6StatBotChat as Chat
import ww6StatBotPlayer

__all__ = [
    'SQLManager',
]


class SQLManager:

    def __init__(self, database):
        self.database = database
        conn = sql.connect(database)
        cur = conn.cursor()
        cur.executescript(
            'CREATE TABLE IF NOT EXISTS users(uid integer UNIQUE on conflict REPLACE, username text, nic text);'
            'CREATE TABLE IF NOT EXISTS blacklist(uid integer UNIQUE on conflict IGNORE);'
            'CREATE TABLE IF NOT EXISTS admins(uid integer UNIQUE on conflict IGNORE);'
            'CREATE TABLE IF NOT EXISTS raids(uid integer references users(uid) on delete CASCADE, time text);'
            'CREATE TABLE IF NOT EXISTS building(uid integer references users(uid) on delete CASCADE, time text);'
            'CREATE TABLE IF NOT EXISTS karma(uid integer references users(uid) on delete CASCADE, time text, value integer);'
            'CREATE TABLE IF NOT EXISTS user_stats(id integer primary key, '
            'uid integer references users(uid) on delete CASCADE, time text UNIQUE on conflict REPLACE,'
            'hp integer, attack integer, armor integer, power integer, accuracy integer,'
            'oratory integer, agility integer, stamina integer);'
            'CREATE TABLE IF NOT EXISTS chats(name text UNIQUE ON CONFLICT IGNORE, chat_id integer, full_name text, type text);'
            'CREATE TABLE IF NOT EXISTS masters(uid integer references users(uid) on delete CASCADE,'
            'name text references chats(name) ON DELETE CASCADE);'
            'CREATE TABLE IF NOT EXISTS chat_members(uid integer references users(uid) on delete CASCADE,'
            'name text references chats(name) ON DELETE CASCADE);'
            'CREATE TABLE IF NOT EXISTS user_settings(uid integer references users(uid) on delete CASCADE UNIQUE on conflict REPLACE,'
            'sex text, notifications int);'
            'CREATE TABLE IF NOT EXISTS user_keyboard(uid integer references users(uid) on delete CASCADE UNIQUE on conflict REPLACE,'
            'state int);'
            'CREATE TABLE IF NOT EXISTS triggers(trigger text, chat text, text text); ')  # TODO also include raid specific tables after refactoring of pin and Daily Challenge tables
        conn.commit()
        conn.close()

    @staticmethod
    def _get_keyboard(cur: sql.Cursor, uid):
        cur.execute('select state from user_keyboard where uid = ?', (uid,))
        r = cur.fetchone()
        return r[0] if r else ww6StatBotPlayer.Player.KeyboardType.DEFAULT

    @staticmethod
    def _get_raids(cur: sql.Cursor, uid):
        cur.execute('select COUNT(*) from raids where uid = ?', (uid,))
        r = cur.fetchone()
        return r[0] if r else 0

    @staticmethod
    def _get_building(cur: sql.Cursor, uid):
        cur.execute('select COUNT(*) from building where uid = ?', (uid,))
        r = cur.fetchone()
        return r[0] if r else 0

    @staticmethod
    def _get_karma(cur: sql.Cursor, uid):
        cur.execute('select SUM(value) from karma where uid = ?', (uid,))
        r = cur.fetchone()
        return r[0] if r else 0

    @staticmethod
    def _get_latest_stats(cur: sql.Cursor, uid):
        cur.execute(
            'select * from user_stats where uid = {0} and time = (SELECT max(time)'
            ' FROM user_stats where uid = {0})'.format(uid))
        r = cur.fetchone()
        st = ww6StatBotPlayer.PlayerStat()
        stid = None
        if r:
            stid, uid, st.time, st.hp, st.attack, st.armor, st.power, st.accuracy, st.oratory, st.agility, st.stamina = r
        return stid, st

    def get_player(self, pl: ww6StatBotPlayer.Player, conn: sql.Connection = None):  # ! pl is modified
        opened = False
        if conn is None:
            opened = True
            conn = sql.connect(self.database)
        cur = conn.cursor()
        uid = pl.uid
        if not pl.nic or not pl.username:
            cur.execute('select * from users where uid = ?', (uid,))
            r = cur.fetchone()
            pl.uid, pl.username, pl.nic = r
        pl.keyboard = ww6StatBotPlayer.Player.KeyboardType(self._get_keyboard(cur, uid))
        pl.raids = self._get_raids(cur, uid)
        pl.building = self._get_raids(cur, uid)
        pl.karma = self._get_karma(cur, uid)
        _, pl.stats = self._get_latest_stats(cur, uid)
        if opened:
            conn.close()
        return pl

    def get_all_players(self):
        conn = sql.connect(self.database)
        players = {}
        cur = conn.cursor()
        cur.execute('SELECT * from users')
        for r in cur.fetchall():
            uid, username, nic = r
            players[uid] = ww6StatBotPlayer.Player()
            pl = players[uid]
            pl.uid = uid
            pl.username = username
            pl.nic = nic
            self.get_player(pl, conn)
        conn.close()
        return players

    def get_all_chats(self):
        conn = sql.connect(self.database)
        result = []
        cur = conn.cursor()
        cur.execute('SELECT * from chats')
        for r in cur.fetchall():
            name, chat_id, full_name, chat_type = r
            chat = Chat.Chat()
            chat.name, chat.chat_id, chat.title = name, chat_id, full_name
            chat.chat_type = Chat.str_to_chat_type(chat_type)
            result.append(chat)
        conn.close()
        return result

    def get_all_masters_uids(self):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        result = {}
        cur.execute('SELECT * from masters')
        for r in cur.fetchall():
            uid, name = r
            if name not in result.keys():
                result[name] = set()
            result[name].add(uid)
        conn.close()
        return result

    def get_all_chat_members_uids(self):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        result = {}
        cur.execute('SELECT * from chat_members')
        for r in cur.fetchall():
            uid, name = r
            if name not in result.keys():
                result[name] = set()
            result[name].add(uid)
        conn.close()
        return result

    def add_blacklist(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('INSERT into blacklist(uid) values(?)', (uid, ))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def get_blacklist(self):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT * from blacklist')
        res = list(cur.fetchall())
        conn.close()
        return res

    def add_admin(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('INSERT into admins(uid) values(?)', (uid, ))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def get_admins(self):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT * from admins')
        res = [r[0] for r in cur.fetchall()]
        conn.close()
        return res
    
    def del_admin(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('DELETE from admins where uid = ?', (uid,))
        conn.commit()
        conn.close()

    def update_user(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        username = pl.username
        nic = pl.nic
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('UPDATE users set username = ?, nic = ? where uid = ?', (username, nic, uid))
        conn.commit()
        conn.close()

    def add_user(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        username = pl.username
        nic = pl.nic
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('INSERT into users(uid, username, nic) values(?, ?, ?)', (uid, username, nic))
        conn.commit()
        conn.close()

    def del_user(self, pl: ww6StatBotPlayer.Player):
        uid = pl.uid
        conn = sql.connect(self.database)
        cur = conn.cursor()
        cur.execute('DELETE from users where uid = ?', (uid,))
        conn.commit()
        conn.close()

    def add_master(self, pl: ww6StatBotPlayer.Player, ch: Chat.Chat):
        uid = pl.uid
        name = ch.name
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('INSERT into masters(uid, name) values(?, ?)', (uid, name))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def del_master(self, pl: ww6StatBotPlayer.Player, ch: Chat.Chat):
        uid = pl.uid
        name = ch.name
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('DELETE from masters where uid = ? and name = ?', (uid, name))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def add_chat(self, ch: Chat.Chat):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('INSERT into chats(name, chat_id, full_name, type) values(?, ?, ?, ?)',
                        (ch.name, ch.chat_id, ch.title, Chat.chat_type_to_str(ch.chat_type)))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def update_chat(self, ch: Chat.Chat):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('UPDATE chats set chat_id = ?, full_name = ?, type = ? where name = ?',
                        (ch.chat_id, ch.title, Chat.chat_type_to_str(ch.chat_type), ch.name))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def del_chat(self, ch: Chat.Chat):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('DELETE from chats where name = ?', (ch.name,))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def add_chat_member(self, pl: ww6StatBotPlayer.Player, ch: Chat.Chat):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('INSERT into chat_members(uid, name) values(?, ?)',
                        (pl.uid, ch.name))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def del_chat_member(self, pl: ww6StatBotPlayer.Player, ch: Chat.Chat):
        conn = sql.connect(self.database)
        cur = conn.cursor()
        try:
            cur.execute('DELETE  from chat_members where uid = ? and name = ?',
                        (pl.uid, ch.name))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

    def update_stats(self, pl: ww6StatBotPlayer.Player):
        st = pl.stats
        uid = pl.uid
        conn = sql.connect(self.database)
        try:
            cur = conn.cursor()
            cur.execute(
                'INSERT into user_stats(uid, time, hp, attack, armor, power, accuracy, oratory, agility, stamina) '
                'values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (uid, st.time, st.hp, st.attack, st.armor, st.power, st.accuracy, st.oratory, st.agility, st.stamina))
        except sql.Error as e:
            raise Exception("Sql error occurred: " + e.args[0])
        conn.commit()
        conn.close()

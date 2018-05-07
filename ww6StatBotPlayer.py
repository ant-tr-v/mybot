import sqlite3 as sql
import datetime
from enum import Enum


class PlayerStat:
    def __init__(self, cur=None, stat_id=None):
        self.time = datetime.datetime.now()
        self.hp = 0
        self.attack = 0
        self.deff = 0
        self.power = 0
        self.accuracy = 0
        self.oratory = 0
        self.agility = 0
        self.raids = 0
        self.id = stat_id
        if cur:
            try:
                cur.execute("CREATE TABLE IF NOT EXISTS userstats"
                            "(id INTEGER PRIMARY KEY,"
                            "time TEXT, hp INTEGER, attack  INTEGER, deff INTEGER, power INTEGER, accuracy INTEGER, "
                            "oratory INTEGER, agility INTEGER, raids INTEGER)")

                if self.id:
                    self.get(cur)
            except sql.Error as e:
                print("Sql error occurred:", e.args[0])

    def put(self, cur):
        try:
            cur.execute("INSERT INTO userstats(time, hp, attack, deff, power, accuracy, oratory, agility, raids)"
                        " VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (self.time, self.hp, self.attack, self.deff, self.power, self.accuracy, self.oratory,
                         self.agility, self.raids))
            self.id = cur.lastrowid
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def get(self, cur):
        try:
            cur.execute("SELECT * FROM userstats WHERE id=?", (self.id,))
            self.time, self.hp, self.attack, self.deff, self.power, self.accuracy, self.oratory, self.agility, \
            self.raids = cur.fetchone()[1:10]
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def update_stats(self, cur):
        try:
            cur.execute("""UPDATE userstats SET
                        time = ? , hp = ? , attack = ? , deff = ? , power = ? , accuracy = ? , oratory = ? ,
                        agility = ? WHERE id=?""",
                        (self.time, self.hp, self.attack, self.deff, self.power, self.accuracy,
                         self.oratory, self.agility, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def update_raids(self, cur, raid_id=None, time=None):
        try:
            cur.execute("""UPDATE userstats SET raids = ?  WHERE id=?""", (self.raids, self.id))
            if time is not None:
                cur.execute("INSERT INTO raids(id, time) VALUES(?, ?)", (raid_id, time))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def sum(self):
        return self.hp + self.attack + self.agility + self.accuracy + self.oratory

    def copy_stats(self, ps):
        self.time, self.hp, self.attack, self.deff, self.power, self.oratory, self.agility, self.accuracy, self.raids = \
            ps.time, ps.hp, ps.attack, ps.deff, ps.power, ps.oratory, ps.agility, ps.accuracy, ps.raids


class PlayerSettings:
    """sex and notifications should be maneged manually, after that update should be called"""

    def __init__(self, cur: sql.Cursor, uid=None):
        self.uid = uid
        self.sex = "male"
        self._notiff_bits = 0
        self.notif_time = ["23:00", "0:00", "1:05", "7:00", "8:00", "9:05", "15:00", "16:00", "17:05"]
        self.notifications = {t: False for t in self.notif_time}
        cur.executescript('CREATE TABLE IF NOT EXISTS user_settings(id INTEGER UNIQUE ON CONFLICT REPLACE, sex TEXT, '
                          'nbits INT, meta TEXT)')
        if not uid:
            return
        cur.execute("SELECT * FROM user_settings WHERE id=?", (self.uid,))
        if len(cur.fetchall()) > 0:
            self.get(cur)
        else:
            self.put(cur)

    def put(self, cur):
        if not self.uid:
            return
        try:
            cur.execute("INSERT INTO user_settings(id, sex, nbits, meta) VALUES(?, ?, ?, ?)",
                        (self.uid, self.sex, self._notiff_bits, ""))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def get(self, cur):
        if not self.uid:
            return
        try:
            cur.execute("SELECT * FROM user_settings WHERE id=?", (self.uid,))
            self.sex, self._notiff_bits = cur.fetchone()[1:-1]
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        k = 1
        for i in range(len(self.notif_time)):
            if k & self._notiff_bits:
                self.notifications[self.notif_time[i]] = True
            else:
                self.notifications[self.notif_time[i]] = False
            k <<= 1

    def update(self, cur=None):
        k = 1
        self._notiff_bits = 0
        for i in range(len(self.notif_time)):
            if self.notifications[self.notif_time[i]]:
                self._notiff_bits |= k
            k <<= 1
        if not self.uid or cur is None:
            return
        try:
            cur.execute("UPDATE user_settings SET sex = ?, nbits = ?, meta = ? WHERE id=?",
                        (self.sex, self._notiff_bits, "", self.uid))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])


class Player:
    class KeyboardType(Enum):
        NONE = -1
        DEFAULT = 0
        TOP = 1
        STATS = 2
        SETTINGS = 3

    def __init__(self, cur: sql.Cursor, setings=(None, -1, "", "", "", [None, None, None, None, None])):
        self.id, self.chatid, self.username, self.nic, self.squad, sids = setings
        if self.squad is None:
            self.squad = ""
        if self.nic is None:
            self.nic = ""
        if self.username is None:
            self.username = ""
        self.update_text(cur)
        self.stats = [PlayerStat(cur, i) if i is not None else None for i in sids]
        self.keyboard = self.KeyboardType.DEFAULT
        self.settings = PlayerSettings(cur, self.id)

    def get_stats(self, n):
        return self.stats[n]

    def set_stats(self, cur, ps: PlayerStat, n):
        if self.stats[n] is None:
            self.stats[n] = PlayerStat(cur)
            self.stats[n].copy_stats(ps)
            self.stats[n].put(cur)
            self.update_id(cur, n)
            return self.stats[n]
        else:
            self.stats[n].copy_stats(ps)
            self.stats[n].update_stats(cur)
            self.stats[n].update_raids(cur)
            self.update_id(cur, n)
            return self.stats[n]

    def update_id(self, cur, n):
        try:
            if n == 0:
                cur.execute("UPDATE users SET id1= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 1:
                cur.execute("UPDATE users SET id2= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 2:
                cur.execute("UPDATE users SET id3= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 3:
                cur.execute("UPDATE users SET lid= ? WHERE id = ?", (self.stats[n].id, self.id))
            elif n == 4:
                cur.execute("UPDATE users SET cid= ? WHERE id = ?", (self.stats[n].id, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def update_text(self, cur):
        try:
            cur.execute("UPDATE users SET username = ?, nic = ?, squad = ? WHERE id = ?",
                        (self.username, self.nic, self.squad, self.id))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def delete(self, cur):
        try:
            cur.execute("DELETE FROM users WHERE id=?", (self.id,))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1
        for st in self.stats:
            if st is not None:
                try:
                    cur.execute("DELETE FROM userstats WHERE id=?", (st.id,))
                except sql.Error as e:
                    print("Sql error occurred:", e.args[0])
                    return -1

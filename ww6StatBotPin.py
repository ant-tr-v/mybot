import telegram as telega
import sqlite3 as sql
import threading
import time
from ww6StatBotPlayer import Player
from time import time
import json
from enum import IntEnum
from ww6StatBotPlayer import Player
from ww6StatBotUtils import MessageManager, Timer


def power(player: Player):
    ps = player.stats[4]
    return ps.attack + ps.hp + ps.deff + ps.agility + 10

"""
ghosts are players that are not actually in pin, their uid is lower then 0 but equal to actual id 
"""

class PinOnlineKm:
    class PlayerStatus(IntEnum):
        SCARED = -2
        SKIPPING = -1
        GOING = 0
        ONPLACE = 1
        UNKNOWN = -100

    def __init__(self, squads: dict, players: dict, message_matager: MessageManager, database, timer:Timer = None,
                 conn=None):
        self.is_active = True
        self.message_manager = message_matager
        self.squads = squads
        self.players = players
        self.db = database
        self.ordered_kms = ['5', '9', '12', '16', '20', '24', '28', '32', '38', '46']
        self.players_online = {}  # dictionary of pairs {'km':km, 'squad':squad, 'state':state)
        self.clear()
        self.messages = {}
        self.copies = {}
        self.chat_messages = {}
        self.commit_lock = threading.Lock()
        self.update_lock = threading.Lock()
        self.chats_to_update = set()
        self.users_to_add = {}  # same format as players_online
        self.users_to_delete = set()
        self.timer = timer or Timer()
        self.task_id = self.timer.add(self._commit, 15)
        self.timer.start()
        self._markup = [
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[:3]],
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[3:6]],
            [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[6:]],
            [telega.InlineKeyboardButton(text="B пути 🐌", callback_data="going_pin"),
             telega.InlineKeyboardButton(text=" На месте 🏕️", callback_data="onplace_pin")],
            [telega.InlineKeyboardButton(text="Ой все 🖕", callback_data="skipping_pin")],
            [telega.InlineKeyboardButton(text="Далеко и опасно 😨", callback_data=" scared_pin")]]
        if conn is None:
            conn = sql.connect(database)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS players_online(id INTEGER UNIQUE ON CONFLICT REPLACE, km TEXT, data TEXT)")
        cur.execute('CREATE TABLE IF NOT EXISTS  pin_json(json TEXT)')
        cur.execute('SELECT * FROM pin_json')
        if len(cur.fetchall()) == 0:
            cur.execute('INSERT INTO pin_json(json) values("[{}, {}, {}]")')
        conn.commit()
        self.is_active = self._upload(conn)

    def clear(self):
        self.players_unconfirmed = {sq: {km: [] for km in self.ordered_kms} for sq in
                                    self.squads.keys()}  # dictionary of ids stored for each squad
        self.players_confirmed = {sq: {km: [] for km in self.ordered_kms} for sq in self.squads.keys()}
        self.players_skipping = {sq: [] for sq in self.squads.keys()}
        self.players_scared = {sq: [] for sq in self.squads.keys()}
        self.players_on_km_confirmed = {km: [] for km in self.ordered_kms}
        self.players_on_km_unconfirmed = {km: [] for km in self.ordered_kms}
        self.powers_on_km_unconfirmed = {km: 0 for km in self.ordered_kms}
        self.powers_on_km_confirmed = {km: 0 for km in self.ordered_kms}

    def player_status(self, player: Player):
        if player.id in self.players_online.keys():
            return self.players_online[player.id]['state']
        return self.PlayerStatus.UNKNOWN

    def add(self, uid, km, squad, recount=True):
        if uid not in self.players.keys() or km not in self.ordered_kms or squad not in self.squads.keys():
            return True
        if self.players[uid].squad != squad and squad != 'spec':  # SpecOp SPECIAL
            self.message_manager.send_message(chat_id=uid, text="Пожалуйста, отмечайся в пине своего отряда")
            return True
        if uid in self.players_online.keys() and self.players_online[uid]['km'] == km \
                and self.players_online[uid]['squad'] == squad:
            return False
        if uid in self.players_online.keys():
            if squad != 'spec' or self.players_online[uid]['squad'] == 'spec':
                self.chats_to_update.add(self.players_online[uid]['squad'])
            else:
                plo = self.players_online[uid]
                self.players_online[-uid] = {'km': plo['km'], 'squad': plo['squad'], 'state': plo['state']}  # New ghost
                self.users_to_add[-uid] = self.players_online[uid]
        if squad != 'spec' and -uid in self.players_online.keys():
            self.chats_to_update.add(self.players_online[-uid]['squad'])
            del(self.players_online[-uid])  # No more ghost
        self.players_online[uid] = {'km': km, 'squad': squad, 'state': self.PlayerStatus.GOING}
        self.users_to_add[uid] = self.players_online[uid]
        if recount:
            self.recount()
        self.chats_to_update.add(squad)
        self.update()
        return True

    def change_status(self, uid, squad, status):
        if status == self.PlayerStatus.SKIPPING or status == self.PlayerStatus.SCARED:
            if uid in self.players_online.keys() and self.players_online[uid]['state'] == status:
                self.delete(uid, self.players_online[uid]['squad'])
                return True
            if -uid in self.players_online.keys() and self.players_online[-uid]['state'] == status and\
                    squad == self.players_online[-uid]['squad']:
                self.delete(-uid, self.players_online[-uid]['squad'])
                return True
            if -uid in self.players_online.keys() and squad == self.players_online[-uid]['squad']:
                self.delete(-uid, squad, False)
                self.players_online[-uid] = {'km': self.ordered_kms[1], 'squad': squad, 'state': status}
            else:
                self.delete(uid, squad, False)
                self.players_online[uid] = {'km': self.ordered_kms[1], 'squad': squad, 'state': status}
        elif uid not in self.players_online.keys() and -uid not in self.players_online.keys():
            return False
        elif -uid in self.players_online.keys():
            if squad == self.players_online[-uid]['squad']:
                self.players_online[-uid]['state'] = status
                self.users_to_add[-uid] = self.players_online[-uid]
                self.chats_to_update.add(squad)
                self.recount()
                self.update()
                return True
            else:
                self.players_online[uid]['state'] = status
        else:
            self.players_online[uid]['state'] = status
        self.users_to_add[uid] = self.players_online[uid]
        self.recount()
        self.chats_to_update.add(squad)
        self.update()
        return True

    def delete(self, uid, squad, recount=True):
        if uid in self.players_online.keys():
            squad = self.players_online[uid]['squad']
            del (self.players_online[uid])
        if -uid in self.players_online.keys() and squad == self.players_online[-uid]['squad']:
            squad = self.players_online[-uid]['squad']
            del (self.players_online[-uid])
        if recount:
            self.recount()
            self.users_to_delete.add(uid)
        self.chats_to_update.add(squad)
        self.update()

    def _commit(self):
        del_list = self.users_to_delete.copy()
        add_list = self.users_to_add.copy()
        self.users_to_delete.clear()
        self.users_to_add.clear()
        conn = sql.connect(self.db)
        cur = conn.cursor()
        try:
            for uid in del_list:
                cur.execute('DELETE FROM players_online WHERE id = ?', (uid,))
            for uid, pl in add_list.items():
                cur.execute('INSERT INTO players_online(id, km, data) VALUES(?, ?, ?)',
                            (uid, pl['km'], '{} {}'.format(pl['squad'], str(pl['state'].value))))
            cur.execute('UPDATE pin_json set json = ?',
                        (json.dumps([self.messages, self.copies, self.chat_messages]),))
            conn.commit()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def _upload(self, conn: sql.Connection):
        cur = conn.cursor()
        cur.execute('SELECT * from pin_json')
        a, c, d = json.loads(cur.fetchone()[0])
        if not a:
            return False
        self.messages = {int(key): v for key, v in a.items()}
        self.copies = {int(key): v for key, v in c.items()}
        self.chat_messages = {key: v for key, v in d.items()}
        cur.execute('SELECT * from players_online')
        for row in cur.fetchall():
            sq, state = row[2].split()
            self.players_online[row[0]] = {'km': row[1], 'squad': sq, 'state': self.PlayerStatus(int(state))}
        self.recount()
        return True

    def recount(self):
        self.clear()
        for uid in list(self.players_online.keys()):
            if uid not in self.players.keys() and -uid not in self.players.keys():
                self.delete(uid, self.players_online[uid]['squad'], recount=False)
                continue
            pl = self.players_online[uid]
            km, squad, state = pl['km'], pl['squad'], pl['state']
            pw = power(self.players[uid]) if uid > 0 else 0
            if state == self.PlayerStatus.GOING:
                self.players_unconfirmed[squad][km].append(uid)
                self.powers_on_km_unconfirmed[km] += pw
                if uid > 0:
                    self.players_on_km_unconfirmed[km].append(uid)
            elif state == self.PlayerStatus.ONPLACE:
                self.players_confirmed[squad][km].append(uid)
                self.powers_on_km_confirmed[km] += pw
                if uid > 0:
                    self.players_on_km_confirmed[km].append(uid)
            elif state == self.PlayerStatus.SKIPPING:
                self.players_skipping[squad].append(uid)
            elif state == self.PlayerStatus.SCARED:
                self.players_scared[squad].append(uid)

    def pin(self, sq, admin: Player, chat_message=""):
        self.is_active = True
        admin_chat = admin.chatid
        if sq not in self.squads.keys():
            self.message_manager.send_message(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        self.chat_messages[sq] = chat_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if self.squads[sq] in self.messages.keys():
            self.message_manager.send_message(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            self.chats_to_update.add(sq)
            self.update()
            return
        text = "#пинонлайн\n<b>{}</b>".format(self.chat_messages[sq])
        id = 0
        try:
            id = self.message_manager.bot.send_message(chat_id=self.squads[sq], text=text,
                                      reply_markup=telega.InlineKeyboardMarkup(self._markup), parse_mode='HTML').message_id
        except:
            pass
        self.messages[self.squads[sq]] = id
        try:
            self.message_manager.bot.pinChatMessage(chat_id=self.squads[sq], message_id=id)
        except:
            self.message_manager.send_message(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.message_manager.send_message(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def _players_in_squad(self, squad):
        """returns confirmed, total number of players + confirmed, total power, string of usernames"""
        cpl = tpl = cpw = tpw = 0
        ulist = []
        for km, uonkm in list(self.players_confirmed[squad].items()):
            for uid in list(uonkm):
                if uid not in self.players.keys():
                    if uid > 0:
                        self.delete(uid, squad, recount=False)
                    continue
                cpl += 1
                tpl += 1
                pl = self.players[abs(uid)]
                pw = power(pl)
                cpw += pw
                tpw += pw
                ulist.append('@' + pl.username)
        ulist.append('|')
        for km, uonkm in list(self.players_unconfirmed[squad].items()):
            for uid in list(uonkm):
                if uid not in self.players.keys():
                    if uid > 0:
                        self.delete(uid, squad, recount=False)
                    continue
                tpl += 1
                pl = self.players[uid]
                tpw += power(pl)
                ulist.append('@' + pl.username)
        return cpl, tpl, cpw, tpw, " ".join(ulist)

    def text(self):
        s1 = "<b>Пины</b>\n{}\n".format(
            "\n".join(["{}: <b>{}</b>".format(m[0], m[1]) for m in list(self.chat_messages.items())]))
        s2 = "<b>Силы на данный момент:</b>\n"
        for sq in list(self.chat_messages.keys()):
            cpl, tpl, cpw, tpw, text = self._players_in_squad(sq)
            s2 += "{}:<b>{}/{}</b>🕳 ({}/{}) {}\n".format(sq, cpl, tpl, cpw, tpw, text)
        s3 = "<b>Локации:</b>\n"
        for km in self.ordered_kms:
            s3 += "<b>{}км</b>({}/{}) [{}/{}] {} | {}\n".format(km, len(self.players_on_km_confirmed[km]),
                                                                len(self.players_on_km_confirmed[km])
                                                                + len(self.players_on_km_unconfirmed[km]),
                                                                self.powers_on_km_confirmed[km],
                                                                self.powers_on_km_confirmed[km] +
                                                                self.powers_on_km_unconfirmed[km],
                                                                " ".join(['@' + self.players[uid].username for uid in
                                                                          self.players_on_km_confirmed[km]]) ,
                                                                " ".join(['@' + self.players[uid].username for uid in
                                                                          self.players_on_km_unconfirmed[km]]))
        return s1, s2, s3

    def copy_to(self, chat_id):
        text = list(self.text())
        ids = []
        for msg in text:
            ids.append(self.message_manager.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML").message_id)
        self.copies[chat_id] = ids.copy()

    def update_squad(self, sq):
        lines = []
        total = 0
        for km in self.ordered_kms:
            if sq != 'spec':
                c = ["@" + self.players[abs(uid)].username + "🏕️" for uid in list(self.players_confirmed[sq][km])]
                u = ["@" + self.players[abs(uid)].username + "🐌" for uid in list(self.players_unconfirmed[sq][km])]
            else:
                c = ["@" + self.players[uid].username + "🏕️" for uid in list(self.players_confirmed[sq][km]) if uid > 0]
                u = ["@" + self.players[uid].username + "🐌" for uid in list(self.players_unconfirmed[sq][km]) if uid > 0]
            if c or u:
                lines.append("<b>" + km + "км</b>(" + str(len(c) + len(u)) + ")" + " ".join(c) + " ".join(u))
                total += len(c) + len(u)
            else:
                lines.append("<b>" + km + "км</b> (0) ---")
        if self.players_skipping[sq]:
            lines.append("\nЭти <i>оригиналы</i> решили, что могут не ходить на рейд:" + " ".join(
                "@" + self.players[abs(uid)].username for uid in list(self.players_skipping[sq])))
        if self.players_scared[sq]:
            lines.append("\nБоятся уходить так далеко от дома:" + " ".join(
                "@" + self.players[abs(uid)].username for uid in list(self.players_scared[sq])))
        text = "#пинонлайн\n<b>{}</b>\n\nонлайн ({})\n{}".format(self.chat_messages[sq], total, "\n".join(lines))
        try:
            self.message_manager.update_msg(timeout=2, chat_id=self.squads[sq], message_id=self.messages[self.squads[sq]], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(self._markup), parse_mode='HTML')
        except telega.TelegramError as e:
            pass  # print(e.message)

    def update(self):
        cpy = self.chats_to_update.copy()
        self.chats_to_update.clear()
        for sq in cpy:
            self.update_squad(sq)
        text = list(self.text())
        for chat_id, msg_ids in self.copies.items():
            for i in range(len(msg_ids)):
                self.message_manager.update_msg(timeout=2, chat_id=chat_id, message_id=msg_ids[i], text=text[i], parse_mode='HTML')

    def close(self):
        self.is_active = False
        for m in self.messages.items():
            try:
                self.message_manager.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        try:
            self.update()
        except:
            pass
        self.timer.delete(self.task_id)
        try:
            conn = sql.connect(self.db)
            conn.execute('DROP TABLE players_online')
            conn.execute('DROP TABLE pin_json')
            conn.commit()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

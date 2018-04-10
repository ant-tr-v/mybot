import telegram as telega
import sqlite3 as sql
import threading
import time
from enum import IntEnum
from ww6StatBotPlayer import Player


def power(player: Player):
    ps = player.stats[4]
    return ps.attack + ps.hp + ps.deff + ps.agility + 10


class PinOnlineKm:
    class PlayerStatus(IntEnum):
        SKIPPING = -1
        GOING = 0
        ONPLACE = 1
        UNKNOWN = -2

    def __init__(self, squads: dict, players: dict, bot: telega.Bot, database):
        self.bot = bot
        self.squads = squads
        self.players = players
        self.db = database
        self.users = {}
        self.ordered_kms = ['3', '7', '10', '12', '15', '19', '22', '29', '36']
        self.players_online = {}  # dictionary of pairs {'km':km, 'squad':squad, 'state':state)
        self.players_names = {sq: [[] for km in self.ordered_kms] for sq in self.squads.keys()}  # dictionary of
        # usernames stored for each squad in the order of ordered_kms
        self.powers_on_km = {km: 0 for km in self.ordered_kms}
        self.powers_on_km_confirmed = {km: 0 for km in self.ordered_kms}
        self.powers_on_squad = {sq: 0 for sq in self.squads.keys()}
        self.messages = {}
        self.connections = {}
        self.copies = {}
        self.chat_messages = {}
        self.update_cooldown_state = False
        self.commit_cooldown_state = False
        self.update_planed = False
        self.commit_planed = False
        self.chats_to_update = set()
        self.users_to_add = {}  # same format as players_online
        self.users_to_delete = set()
        self._markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in self.ordered_kms[6:]],
                  [telega.InlineKeyboardButton(text="B пити", callback_data="going_state"),
                   telega.InlineKeyboardButton(text=" На месте", callback_data="onplace_state"),
                   telega.InlineKeyboardButton(text="Ой все", callback_data="skipping_state")]]
        conn = sql.connect(database)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS players_online(id INTEGER UNIQUE ON CONFLICT REPLACE, km TEXT, data TEXT)")
        conn.commit()
        self._upload(conn)

    def add(self, uid, km, squad, recount=True):
        if uid in self.users_to_delete:
            self.users_to_delete.remove(uid)
        if uid not in self.players.keys() or km not in self.ordered_kms or squad not in self.squads.keys():
            return
        self.players_online[uid] = {'km': km, 'squad': squad, 'state': self.PlayerStatus.GOING}
        self.users_to_add[uid] = self.players_online[uid]
        if recount:
            self.recount()
        self.commit()

    def delete(self, uid, recount=True):
        if uid in self.users_to_add.keys():
            del (self.users_to_add[uid])
        if uid in self.players_online.keys():
            del (self.players_online[uid])
        if recount:
            self.recount()
        self.commit()

    def commit(self):
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
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

    def _upload(self, conn: sql.Connection):
        cur = conn.cursor()
        cur.execute('SELECT * from players_online')
        for row in cur.fetchall():
            sq, state = row[2].split()
            self.players_online[row[0]] = {'km': row[1], 'squad': sq, 'state': self.PlayerStatus(int(state))}

    def recount(self):
        self.powers_on_km = {km: 0 for km in self.ordered_kms}
        self.powers_on_squad = {sq: 0 for sq in self.squads.keys()}
        self.players_names = {sq: [[] for km in self.ordered_kms] for sq in self.squads.keys()}
        for uid in list(self.players_online):
            if uid not in self.players.keys():
                self.delete(uid, recount=False)
                continue
            pl = self.players_online[uid]
            km, squad, state = pl['km'], pl['squad'], pl['state']
            pw = power(self.players[uid])
            name = self.players[uid].username
            self.players_names[squad][self.ordered_kms.index(km)].append(name)
            self.powers_on_km[km] += pw
            self.powers_on_squad[squad] += pw

    def pin(self, sq, admin: Player, chat_message=""):
        admin_chat = admin.chatid
        if admin_chat not in self.connections.keys():
            self.connect(admin_chat)
            self.update()
        if sq not in self.squads.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        self.chat_messages[sq] = chat_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if self.squads[sq] in self.messages.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            self.chats_to_update.add(self.squads[sq])
            self.update()
            return
        text = "#пинонлайн\n<b>{}</b>".format(chat_message[sq])
        id = self.bot.sendMessage(chat_id=self.squads[sq], text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(self._markup), parse_mode='HTML').message_id
        self.messages[self.squads[sq]] = id
        try:
            self.bot.pinChatMessage(chat_id=self.squads[sq], message_id=id)
        except:
            self.bot.sendMessage(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.bot.sendMessage(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def text(self):
        s = "<b>Пины</b>\n"
        for m in self.chatm.items():
            s += " " + m[0] + ": <b>" + m[1] + "</b>\n"
        s += "<b>Силы на данный момент:</b>\n"
        for sq in self.power.keys():
            if self.squadids[sq] in self.messages.keys():
                s += sq + ": <b>" + str(self.power[sq]) + "</b>🕳 (" + str(len(self.names[sq])) + ") "
                if self.names[sq]:
                    s += "[@" + " @".join(self.names[sq]) + "]\n"
                else:
                    s += "\n"
        s += "<b>Локации</b>\n"
        for km in self.ordered_kms:
            if self.kms[km]:
                s += " <b>" + km + "км</b> (" + str(len(self.kms[km])) + ") [" + str(
                    self.kmspw[km]) + "] @" + " @".join(self.kms[km]) + "\n"
            else:
                s += " <b>" + km + "км</b> (0) ---\n"
        return s

    def copy_to(self, chat_id):
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        self.copies[chat_id] = id

    def connect(self, chat_id):
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup)).message_id
        self.connections[chat_id] = id

    def update_chat(self, chat_id):
        sq = self.squabyid[chat_id]
        text = "#пинонлайн\n" + self.mes + "<b>" + self.chatm[sq] + "</b>" + "\n\nонлайн (" + str(
            len(self.names[sq])) + ")\n"
        for km in self.ordered_kms:
            l = [u for u in self.kms[km] if self.users[self.usersbyname[u]][0] == chat_id]
            if l != []:
                text += "<b>" + km + "км</b> (" + str(len(l)) + "): @" + " @".join(l) + "\n"
            else:
                text += "<b>" + km + "км</b> (0) ---\n"
        kms = [x for x in self.ordered_kms]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        try:
            self.bot.editMessageText(chat_id=chat_id, message_id=self.messages[chat_id], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
        except:
            pass

    def unfreeze(self):
        self.cooldownstate = False

    def update(self):
        self.planUpdate = False
        if self.cooldownstate:
            if not self.planUpdate:
                threading.Timer(0.07, self.update).start()
                self.planUpdate = True
            return
        self.cooldownstate = True
        list = self.chats_to_update.copy()
        self.chats_to_update.clear()
        for chat in list:
            self.update_chat(chat)
            time.sleep(1. / 100)
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        for con in self.connections.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text,
                                         reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
            except:
                pass
        for con in self.copies.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text, parse_mode='HTML')
            except:
                pass
        threading.Timer(0.05, self.unfreeze).start()

    def close(self):
        for m in self.messages.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        self.update()
        for m in self.connections.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        conn = sql.connect(self.db)
        conn.execute('DROP TABLE players_online')
        conn.commit()

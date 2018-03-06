# -*- coding: utf-8 -*-
import random
import re

from telegram.ext import Updater
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import CommandHandler
from telegram.ext import CallbackQueryHandler
import telegram as telega
import sqlite3 as sql
import datetime
import threading
import time
from enum import Enum


class KeyboardType(Enum):
    NONE = -1
    DEFAULT = 0
    TOP = 1
    STATS = 2


class StatType(Enum):
    ALL = 1
    ATTACK = 2
    HP = 3
    ACCURACY = 4
    AGILITY = 5
    ORATORY = 6
    RAIDS = 7


class PlayerStat:
    def __init__(self, cur, id=None):
        self.time = datetime.datetime.now()
        self.hp = 0
        self.attack = 0
        self.deff = 0
        self.power = 0
        self.accuracy = 0
        self.oratory = 0
        self.agility = 0
        self.raids = 0
        self.id = id
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

    def update_raids(self, cur, id=None, time=None):
        try:
            cur.execute("""UPDATE userstats SET raids = ?  WHERE id=?""", (self.raids, self.id))
            if time is not None:
                cur.execute("INSERT INTO raids(id, time) VALUES(?, ?)", (id, time))
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
            return -1

    def sum(self):
        return self.hp + self.attack + self.agility + self.accuracy + self.oratory

    def copy_stats(self, ps):
        self.time, self.hp, self.attack, self.deff, self.power, self.oratory, self.agility, self.accuracy, self.raids = \
            ps.time, ps.hp, ps.attack, ps.deff, ps.power, ps.oratory, ps.agility, ps.accuracy, ps.raids


class Player:
    def __init__(self, cur, setings=(None, -1, "", "", "", [None, None, None, None, None])):
        self.id, self.chatid, self.username, self.nic, self.squad, sids = setings
        if self.squad is None:
            self.squad = ""
        if self.nic is None:
            self.nic = ""
        if self.username is None:
            self.username = ""
        self.update_text(cur)
        self.stats = [PlayerStat(cur, i) if i is not None else None for i in sids]
        self.keyboard = KeyboardType.DEFAULT

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


class PinOnline:
    def __init__(self, squadids: dict, bot):
        self.bot = bot
        self.squadids = squadids
        self.squabyid = {v[1]: v[0] for v in self.squadids.items()}
        self.users = {}
        self.power = {sq: 0 for sq in squadids.keys()}
        self.names = {sq: set() for sq in squadids.keys()}
        self.messages = {}
        self.connections = {}
        self.copies = {}

    def pin(self, sq, admin_chat):
        if not admin_chat in self.connections.keys():
            self.connect(admin_chat)
        self.update()
        if sq not in self.squadids.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        if self.squadids[sq] in self.messages.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            return
        markup = [[telega.InlineKeyboardButton(text="Готов 🤺", callback_data="online")]]
        text = "#пинонлайн Готовимся к рейду"
        chat_id = self.squadids[sq]
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup)).message_id
        self.messages[chat_id] = id
        try:
            self.bot.pinChatMessage(chat_id=chat_id, message_id=id)
        except:
            self.bot.sendMessage(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.bot.sendMessage(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def add(self, player: Player, chat_id):
        if player.id in self.users.keys():
            if chat_id != self.users[player.id]:
                self.delete(player)
            else:
                return False
        self.users[player.id] = chat_id
        ps = player.stats[4]
        sq = self.squabyid[chat_id]
        self.power[sq] += ps.attack + ps.hp + ps.deff + ps.agility + 10
        self.names[sq].add(player.username)
        self.update_chat(chat_id)
        self.update()
        return True

    def delete(self, player: Player):
        if player.id not in self.users.keys():
            return False
        sq = self.squabyid[self.users[player.id]]
        ps = player.stats[4]
        self.power[sq] -= (ps.attack + ps.hp + ps.deff + ps.agility + 10)
        self.names[sq].discard(player.username)
        del (self.users[player.id])
        self.update_chat(self.squadids[sq])
        self.update()
        return True

    def text(self):
        s = "Силы на данный момент:\n"
        for sq in self.power.keys():
            if self.squadids[sq] in self.messages.keys():
                s += sq + ": <b>" + str(self.power[sq]) + "</b> Даки-поинтов (" + str(len(self.names[sq])) + ")" + str(
                    self.names[sq]) + "\n"
        return s

    def copy_to(self, chat_id):
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        self.copies[chat_id] = id

    def connect(self, chat_id):
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offline")]]
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup)).message_id
        self.connections[chat_id] = id

    def update_chat(self, chat_id):
        sq = self.squabyid[chat_id]
        text = "#пинонлайн Готовимся к рейду:\nонлайн (" + str(len(self.names[sq])) + ")" + str(self.names[sq]) + "\n"
        markup = [[telega.InlineKeyboardButton(text="Готов 🤺", callback_data="online")]]
        try:
            self.bot.editMessageText(chat_id=chat_id, message_id=self.messages[chat_id], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
        except:
            pass

    def update(self):
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offline")]]
        for con in self.connections.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=self.text(),
                                         reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
            except:
                pass
        for con in self.copies.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=self.text(), parse_mode='HTML')
            except:
                pass

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


class PinOnlineKm:
    def __init__(self, squadids: dict, bot):
        self.bot = bot
        self.mes = ""
        self.squadids = squadids
        self.squabyid = {v[1]: v[0] for v in self.squadids.items()}
        self.users = {}
        self.oderedkm = ['3', '7', '10', '12', '15', '19', '22', '29', '36']
        self.kms = {x: set() for x in self.oderedkm}
        self.kmspw = {x: 0 for x in self.oderedkm}
        self.power = {sq: 0 for sq in squadids.keys()}
        self.names = {sq: set() for sq in squadids.keys()}
        self.messages = {}
        self.connections = {}
        self.copies = {}
        self.usersbyname = {}
        self.chatm = {}

    def pin(self, sq, admin_chat, chatmes=""):
        if not admin_chat in self.connections.keys():
            self.connect(admin_chat)
        self.update()
        if sq not in self.squadids.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        self.chatm[sq] = chatmes
        if self.squadids[sq] in self.messages.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            self.update_chat(self.squadids[sq])
            return
        kms = [x for x in self.oderedkm]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        text = "#пинонлайн\n" + self.mes + "<b>" + self.chatm[sq] + "</b>"
        chat_id = self.squadids[sq]
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML').message_id
        self.messages[chat_id] = id
        try:
            self.bot.pinChatMessage(chat_id=chat_id, message_id=id)
        except:
            self.bot.sendMessage(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.bot.sendMessage(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def add(self, player: Player, chat_id, km):
        if player.id in self.users.keys():
            if (chat_id != self.users[player.id]) and (player.username not in self.kms[km]):
                self.delete(player)
            else:
                return False
        self.users[player.id] = (chat_id, km)
        self.kms[km].add(player.username)
        self.usersbyname[player.username] = player.id
        ps = player.stats[4]
        sq = self.squabyid[chat_id]
        self.power[sq] += ps.attack + ps.hp + ps.deff + ps.agility + 10
        self.kmspw[km] += ps.attack + ps.hp + ps.deff + ps.agility + 10
        self.names[sq].add(player.username)
        self.update_chat(chat_id)
        self.update()
        return True

    def delete(self, player: Player):
        if player.id not in self.users.keys():
            return False
        sq = self.squabyid[self.users[player.id][0]]
        km = self.users[player.id][1]
        ps = player.stats[4]
        self.power[sq] -= (ps.attack + ps.hp + ps.deff + ps.agility + 10)
        self.kmspw[km] -= (ps.attack + ps.hp + ps.deff + ps.agility + 10)
        self.names[sq].discard(player.username)
        self.kms[km].discard(player.username)
        del (self.users[player.id])
        self.update_chat(self.squadids[sq])
        self.update()
        return True

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
        for km in self.oderedkm:
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
        for km in self.oderedkm:
            l = [u for u in self.kms[km] if self.users[self.usersbyname[u]][0] == chat_id]
            if l != []:
                text += "<b>" + km + "км</b> (" + str(len(l)) + "): @" + " @".join(l) + "\n"
            else:
                text += "<b>" + km + "км</b> (0) ---\n"
        kms = [x for x in self.oderedkm]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        try:
            self.bot.editMessageText(chat_id=chat_id, message_id=self.messages[chat_id], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
        except:
            pass

    def update(self):
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


class Bot:
    def __init__(self, database: str, token: str, bot_name: str):
        conn = None
        self.database = database
        self.bot_name = bot_name
        try:
            conn = sql.connect(database)
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users"
                    "(id INT UNIQUE, chatid INT, username TEXT, nic TEXT, squad TEXT, id1 INT, id2 INT, id3 INT, lid INT, cid INT)")
        cur.execute('CREATE TABLE IF NOT EXISTS squads (name TEXT, short TEXT, chatid INT)')
        cur.execute('CREATE TABLE IF NOT EXISTS masters (id INTEGER, name TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER)')
        cur.execute('CREATE TABLE IF NOT EXISTS raids (id INTEGER, time TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS blacklist (id INTEGER)')
        cur.execute(
            'CREATE TABLE IF NOT EXISTS settings (id REFERENCES users(id) ON DELETE CASCADE, sex TEXT, keyboard INT, raidnotes INT)')
        cur.execute('CREATE TABLE IF NOT EXISTS state (data TEXT)')  # not The best solution ever but it will do
        cur.execute("SELECT * FROM admins")
        self.admins = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM blacklist")
        self.blacklist = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM raids")
        self.raids = set((r[0], r[1]) for r in cur.fetchall())
        self.pinonline = None
        self.pinkm = None
        self.usersbyname = {}
        self.masters = {}
        self.users = {}
        self.squadnames = {}
        self.squadids = {}
        self.kick = {}
        self.viva_six = {}
        self.pinns = []  # (squad, pinn, time) or (squad) to unp #TODO написать реализацию
        self.keyboards = {}  # TODO написать админские клавиатуры
        self.keyboards[KeyboardType.DEFAULT] = telega.ReplyKeyboardMarkup([[telega.KeyboardButton("💽 Моя статистика"),
                                                                            telega.KeyboardButton("🎖 Топы")],
                                                                            [telega.KeyboardButton("👻 О боте"),
                                                                             telega.KeyboardButton("👨‍💻 О жизни")]],
                                                                          resize_keyboard=True)
        self.keyboards[KeyboardType.TOP] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("🏅 Рейтинг"), telega.KeyboardButton("⚔️ Дамагеры"),
              telega.KeyboardButton("❤️ Танки")],
             [telega.KeyboardButton("🤸🏽‍♂️ Ловкачи"), telega.KeyboardButton("🔫 Снайперы"),
              telega.KeyboardButton("🗣 Дипломаты")], [telega.KeyboardButton("🔪 Рейдеры")],
             [telega.KeyboardButton("📜 Полный список"), telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        self.keyboards[KeyboardType.STATS] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("📱 Статистика"), telega.KeyboardButton("🔝 Прирост")],
             [telega.KeyboardButton("📲 Сохранить"), telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        self.state = KeyboardType.DEFAULT
        cur.execute("SELECT * FROM users")
        for r in cur.fetchall():
            # print(r)да почитай описание к боту, можно удобно следить за своими статами, бот в процессе допиливания, и будет расширен функционал))) но потом )))
            p = list(r[:5])
            p.append(list(r[5:]))
            self.usersbyname[r[2].lower()] = r[0]
            self.users[r[0]] = Player(cur, p)

        cur.execute("SELECT * FROM masters")
        for r in cur.fetchall():
            if not r[0] in self.masters.keys():
                self.masters[r[0]] = set()
            self.masters[r[0]].add(r[1].lower())
        cur.execute("SELECT * FROM squads")
        for r in cur.fetchall():
            self.squadnames[r[1].lower()] = r[0]
            self.squadids[r[1].lower()] = r[2]
        self.updater = Updater(token=token)
        massage_handler = MessageHandler(Filters.text | Filters.command, self.handle_massage)
        start_handler = CommandHandler('start', self.handle_start)
        callback_handler = CallbackQueryHandler(callback=self.handle_callback)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(massage_handler)
        self.updater.dispatcher.add_handler(callback_handler)
        self.updater.start_polling(clean=True)

    def handle_start(self, bot, update):
        message = update.message
        user = message.from_user
        if message.chat.type != "private":
            return
        if user.id in self.blacklist:
            bot.sendMessage(chat_id=message.chat_id, text="Не особо рад тебя видеть.\nУходи",
                            reply_markup=telega.ReplyKeyboardRemove())
            return
        elif user.id not in self.users.keys():
            bot.sendMessage(chat_id=message.chat_id, text="Привет, давай знакомиться.\nКидай мне форвард своих статов",
                            reply_markup=telega.ReplyKeyboardRemove())
            return
        self.users[user.id].keyboard = KeyboardType.DEFAULT
        bot.sendMessage(chat_id=message.chat_id, text="Рад тебя видеть",
                        reply_markup=self.keyboards[KeyboardType.DEFAULT])

    def add_admin(self, id):
        conn = sql.connect(self.database)
        if not id in self.admins:
            cur = conn.cursor()
            cur.execute("INSERT INTO admins(id) VALUES (?)", (id,))
            self.admins.add(id)
            conn.commit()

    def del_admin(self, id):
        conn = sql.connect(self.database)
        if id in self.admins:
            cur = conn.cursor()
            cur.execute("DELETE FROM admins WHERE id=?", (id,))
            self.admins.remove(id)
            conn.commit()
            return True
        return False

    def ban(self, cur, id, bann_him=True):
        if not id in self.blacklist:
            self.users[id].delete(cur)
            del (self.usersbyname[self.users[id].username.lower()])
            del (self.users[id])
            if (bann_him):
                cur.execute("INSERT INTO blacklist(id) VALUES (?)", (id,))
                self.blacklist.add(id)

    def unbun(self, id):
        conn = sql.connect(self.database)
        if id in self.blacklist:
            cur = conn.cursor()
            cur.execute("DELETE FROM blacklist WHERE id=?", (id,))
            self.blacklist.remove(id)
            conn.commit()
            return True
        return False

    def add_to_squad(self, cur, id, sq):
        self.users[id].squad = sq
        self.users[id].update_text(cur)

    def del_from_squad(self, cur, id):
        self.users[id].squad = ""
        self.users[id].update_text(cur)

    def add_master(self, cur, bot, id, adminid, sq):
        sq = sq.lower()
        if (sq not in self.squadnames.keys()):
            bot.sendMessage(chat_id=self.users[adminid].chatid, text="Нет такого отряда")
            return
        if (adminid not in self.admins) and ((adminid not in self.masters.keys()) or (sq not in self.masters[adminid])):
            bot.sendMessage(chat_id=self.users[adminid].chatid, text="У вас нет на это прав. Возьмите их у Антона")
            return
        if (id in self.masters.keys()) and sq in self.masters[id]:
            bot.sendMessage(chat_id=self.users[adminid].chatid, text="Да он и так командир)")
            return
        cur.execute("INSERT INTO masters(id, name) VALUES (?, ?)", (id, sq))
        self.masters[id].add(sq)

    def add_squad(self, cur, bot, master, short, title, id, chat_id):
        if id not in self.admins:
            bot.sendMessage(chat_id=self.users[id].chatid, text="Хм... А кто тебе сказал что ты так можешь?")
            return
        if master not in self.users.keys():
            bot.sendMessage(chat_id=chat_id, text="Пользователь @" + master + " ещё не зарегестрирован")
            return
        if (short in self.squadnames.keys()) or short == "none":
            bot.sendMessage(chat_id=chat_id, text="Краткое имя \"" + short + "\" уже занято")
            return
        r = (title, short, chat_id)
        cur.execute("INSERT INTO squads(name, short, chatid) VALUES(?, ?, ?)", r)
        self.masters[master] = set()
        self.squadnames[short] = r[0]
        self.squadids[short] = r[2]
        self.add_master(cur, bot, master, id, short)
        bot.sendMessage(chat_id=chat_id,
                        text="Создан отряд " + self.squadnames[short] + " aka " + short)

    def stat(self, bot, id, chat_id, n, textmode=False):
        player = self.users[id]
        ps = player.get_stats(n - 1)
        s = "<b>" + player.nic + "</b>\n"
        if player.squad != "":
            s += "Отряд: <b>" + self.squadnames[player.squad] + "</b>\n"
        if ps is None:
            return "Эта ячейка памяти ещё пуста 🙃"
        s += "<b>От </b>" + str(ps.time) + "\n" \
             "<b>\nЗдоровье:          </b>" + str(ps.hp) + \
             "<b>\nУрон:                   </b>" + str(ps.attack) + \
             "<b>\nБроня:                 </b>" + str(ps.deff) + \
             "<b>\nСила:                   </b>" + str(ps.power) + \
             "<b>\nМеткость:           </b>" + str(ps.accuracy) + \
             "<b>\nХаризма:            </b>" + str(ps.oratory) + \
             "<b>\nЛовкость:           </b>" + str(ps.agility) + \
             "<b>\n\nУспешные рейды:     </b>" + str(ps.raids)
        if textmode:
            return s
        else:
            bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML')

    def change(self, bot, id, chat_id, n, textmode=False):
        if self.users[id].stats[n - 1] is None:
            return "Эта ячейка памяти ещё пуста"
        player = self.users[id]
        ops = player.get_stats(n - 1)
        player = self.users[id]
        ps = player.get_stats(4)
        s = "<b>" + player.nic + "</b>\n" \
            + "Прирост с: " + str(ops.time) + "\nПо: " + str(ps.time)
        if ps.hp - ops.hp:
            s += "<b>\nЗдоровье:          </b>" + str(ps.hp - ops.hp)
        if ps.attack - ops.attack:
            s += "<b>\nУрон:                   </b>" + str(ps.attack - ops.attack)
        if ps.deff - ops.deff:
            s += "<b>\nБроня:                 </b>" + str(ps.deff - ops.deff)
        if ps.power - ops.power:
            s += "<b>\nСила:                   </b>" + str(ps.power - ops.power)
        if ps.accuracy - ops.accuracy:
            s += "<b>\nМеткость:           </b>" + str(ps.accuracy - ops.accuracy)
        if ps.oratory - ops.oratory:
            s += "<b>\nХаризма:            </b>" + str(ps.oratory - ops.oratory)
        if ps.agility - ops.agility:
            s += "<b>\nЛовкость:           </b>" + str(ps.agility - ops.agility)
        if ps.raids - ops.raids:
            s += "<b>\n\nУспешные рейды:     </b>" + str(ps.raids - ops.raids)
        if textmode == True:
            return s
        else:
            bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML')

    def handle_forward(self, cur, bot, message):
        user = message.from_user
        player = self.users[user.id]
        text = message.text.strip(" \n\t")
        player.username = user.username
        self.usersbyname[user.username] = user.id
        tlines = text.split("\n")
        ps = PlayerStat(cur)
        n = -1
        nic = ""
        for i in range(1, len(tlines)):
            if tlines[i] and tlines[i][0] == '├' and tlines[i - 1][0] == '├':
                n = i - 2
                break
        if n >= 0:
            nic = tlines[n][1:]
            ps.hp, hanger, ps.attack, ps.deff = [int("".join([c for c in x if c.isdigit()])) for x in
                                                 tlines[n + 2][tlines[n + 2].find("/"):].split('|')]
            ps.power, ps.accuracy = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n + 3].split('|')]
            ps.oratory, ps.agility = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n + 4].split('|')]
        else:
            nl = 2  # МАГИЧЕСКАЯ КОНСТАНТА номер строки с ником игрока [первый возможный]
            while nl < len(tlines):
                if "Фракция:" in tlines[nl + 1]:
                    break
                nl += 1
            nic = tlines[nl].strip()
            for i in range(nl + 1, len(tlines)):
                m = re.search(r'Здоровье:[\s][\d]+/(?P<val>[\d]+)', tlines[i])
                if m:
                    ps.hp = int(m.group('val'))
                m = re.search(r'Урон:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.attack = int(m.group('val'))
                m = re.search(r'Броня:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.deff = int(m.group('val'))
                m = re.search(r'Сила:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.power = int(m.group('val'))
                m = re.search(r'Меткость:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.accuracy= int(m.group('val'))
                m = re.search(r'Харизма:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.oratory = int(m.group('val'))
                m = re.search(r'Ловкость:[\s](?P<val>[\d]+)', tlines[i])
                if m:
                    ps.agility = int(m.group('val'))
        nic = nic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if player.nic == "":
            player.nic = nic
        elif player.nic != nic:
            bot.sendMessage(chat_id=player.chatid,
                            text="🤔 Раньше ты играл под другим ником.\nЕсли ты сменил игровой ник обратись к @ant_ant\nА инче не кидай мне чужой профиль!")
            return False
        ps.time = message.forward_date
        oldps = player.get_stats(4)
        ps.raids = 0
        if oldps is not None:
            player.set_stats(cur, oldps, 3)
            ps.raids = oldps.raids
        if "Рейд в " in tlines[-3]:
            goone = True
            date = message.forward_date
            try:
                time = tlines[-3].split()[-1]
                ddate = datetime.datetime(year=date.year, month=date.month, day=date.day,
                                          hour=int(time.split(':')[0]) % 24)
                if message.date - ddate < datetime.timedelta(milliseconds=10):
                    ddate = ddate - datetime.timedelta(days=1)
                date = str(ddate).split('.')[0]
            except:
                goone = False
            if goone and ((user.id, date) not in self.raids):
                self.raids.add((user.id, date))
                ps.raids += 1
                ps.update_raids(cur, user.id, date)
                if player.squad in self.squadnames.keys():
                    text = "<b>" + player.nic + "</b> aka @" + player.username + " отличился на рейде \n" + date + "\n" + \
                           tlines[-2] + "\n" + tlines[-1]
                    text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    try:
                        bot.sendMessage(chat_id=self.squadids[player.squad], text=text, parse_mode='HTML')
                    except:
                        try:
                            bot.sendMessage(chat_id=player.chatid,
                                            text="Я не смог отправить сообщение в твой отряд\nЕсли хочешь - отправь его сам:\n\n" + text,
                                            parse_mode='HTML')
                        except:
                            pass
                try:
                    bot.sendMessage(chat_id=player.chatid, text="Засчитан успешный рейд", parse_mode='HTML')
                except:
                    pass
        player.set_stats(cur, ps, 4)
        player.update_text(cur)
        bot.sendMessage(chat_id=player.chatid, text="Я занес твои результаты")
        return True

    def top(self, bot, id, username, chat_id, text, type: StatType, invisible=False, title="",
            time=datetime.datetime.now(), textmode=False):
        arr = []
        s = ""
        if title:
            s = "<b>" + title + ":</b>"
        if type == StatType.ALL:
            if not s:
                s = "<b>Топ игроков:</b>"
            arr = [(pl.get_stats(4).sum(), pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        elif type == StatType.HP:
            if not s:
                s = "<b>Топ танков:</b>"
            arr = [(pl.get_stats(4).hp, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in self.users.values()]
        elif type == StatType.ATTACK:
            if not s:
                s = "<b>Топ дамагеров:</b>"
            arr = [(pl.get_stats(4).attack, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        elif type == StatType.ACCURACY:
            if not s:
                s = "<b>Топ снайперов:</b>"
            arr = [(pl.get_stats(4).accuracy, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        elif type == StatType.AGILITY:
            if not s:
                s = "<b>Топ ловкачей:</b>"
            arr = [(pl.get_stats(4).agility, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        elif type == StatType.ORATORY:
            if not s:
                s = "<b>Топ дипломатов:</b>"
            arr = [(pl.get_stats(4).oratory, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        elif type == StatType.RAIDS:
            if not s:
                s = "<b>Топ рейдеров:</b>"
            arr = [(pl.get_stats(4).raids, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
                   self.users.values()]
        else:
            return
        arr.sort(reverse=True)
        sq = ""
        con1 = True
        cap = False
        admin = id in self.admins
        if text != "" and len(text.split()) != 1:
            sq = text.split()[1].lower()
            cap = id in self.masters.keys() and sq in self.masters[id]
            if self.users[id].squad != sq and not cap and not admin:
                bot.sendMessage(chat_id=chat_id, text="Похоже, это не ваш отряд", parse_mode='HTML')
                return
            if sq in self.squadnames.keys():
                con1 = False
                s = s[:-5] + "</b> отряда <b>" + self.squadnames[sq] + ":</b>"
        i = 1
        sum = 0
        for val, name, nic, squad, lasttime in arr:
            lasttime = str(lasttime)
            lasttime = datetime.datetime.strptime(lasttime.split('.')[0], "%Y-%m-%d %H:%M:%S")
            if con1 or squad == sq:
                if (id in self.admins) or i <= 5 or (con1 and cap) or invisible or name == username:
                    if (id in self.admins) or (con1 and cap):
                        if time - lasttime > datetime.timedelta(days=30):
                            s += "\n" + str(i) + ') ----<a href = "t.me/' + name + '">' + nic + '</a>'
                        elif time - lasttime > datetime.timedelta(days=7):
                            s += "\n" + str(i) + ') ***<a href = "t.me/' + name + '">' + nic + '</a>'
                        elif time - lasttime > datetime.timedelta(days=3):
                            s += "\n" + str(i) + ') **<a href = "t.me/' + name + '">' + nic + '</a>'
                        elif time - lasttime > datetime.timedelta(hours=36):
                            s += "\n" + str(i) + ') *<a href = "t.me/' + name + '">' + nic + '</a>'
                        else:
                            s += "\n" + str(i) + ') <a href = "t.me/' + name + '">' + nic + ' </a>'
                    else:
                        s += "\n" + str(i) + ') <a href = "t.me/' + name + '">' + nic + ' </a>'
                    if (not invisible) and (
                                    id in self.admins or name == username or type == StatType.ALL or type == StatType.RAIDS):
                        s += ": <b>" + str(val) + "</b>"
                    elif not invisible:
                        s += ": <b>" + str(val)[0] + "*" * (len(str(val)) - 1) + "</b>"
                    sum += val
                if i == 5 and not invisible:
                    s += "\n"
                i += 1
        if (id in self.admins or (con1 and cap)) and not invisible:
            s += "\n\nОбщий счет: " + str(sum)
        if not textmode:
            bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML', disable_web_page_preview=True)
        else:
            return s

    def list_squads(self, bot, chat_id, show_pin = False):
        text = ""
        for sqshort, sqname in self.squadnames.items():
            text += "<b>" + sqname + "</b> aka <i>" + sqshort + "</i>"
            if show_pin:
                if self.pinkm and sqshort in self.pinkm.chatm.keys():
                    text += " \t✅"
                else:
                    text+= " \t❌"
            text += "\n"
        bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True)

    def pin(self, bot, chat_id, text, uid):
        id = -1
        try:
            id = bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        except:
            bot.sendMessage(chat_id=uid, text="Не удалось доставить сообщение")
        time.sleep(1)
        try:
            bot.pinChatMessage(chat_id=chat_id, message_id=id)
        except:
            bot.sendMessage(chat_id=uid, text="Я не смог запинить((")
            return
        bot.sendMessage(chat_id=uid, text="Готово\nСообщение в пине")

    def demand_squads(self, text, user, bot):
        if len(text.split()) <= 2:
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="сообщения-то и нехватает")
            return None, None
        split = text.split()
        sqs = []
        start = -1
        for word in split[1:]:
            if word in self.squadnames.keys():
                sqs.append(word)
            else:
                start = text.find(word)
                break
        if not sqs:
            bot.sendMessage(chat_id=self.users[user.id].chatid,
                            text="Весело наверное писать в несуществующий отряд")
            return None, None
        if user.id not in self.admins and user.id not in self.masters.keys() and not any(sq in self.masters[
            user.id] for sq in sqs):
            bot.sendMessage(chat_id=self.users[user.id].chatid,
                            text="Небеса не одарили тебя столь великой властью\nМожешь рискнуть обратиться за "
                                 "ней к Антону")
            return None, None
        if not text[start:]:
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="Но что же мне им написать?")
            return None, None
        return sqs, text[start:]

    def demand_ids(self, text, user, bot, offset=1, all = False):
        """не проверяет на права администратора
        может вернуть пустую строку"""
        if len(text.split()) <= 2:
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="Чего-то здесь не хватает")
            return None, None
        ids = []
        start = -1
        split = text.split()
        for word in split[offset:]:
            if word.strip('@').lower() in self.usersbyname.keys():
                ids.append(self.usersbyname[word.strip('@').lower()])
            elif not all:
                start = text.find(word)
                break
            else:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Не знаю игрока по имени @" + name)

        if not ids:
            bot.sendMessage(chat_id=self.users[user.id].chatid,
                            text="Я не нашёл ни одного юзернейма")
        return text[start:], ids

    def handle_command(self, cur, conn, bot, message):
        text = message.text
        user = message.from_user
        chat_id = message.chat_id
        text0 = text[:text.find(' ')] if text.find(' ') > 0 else text
        text0 = text0[:text0.find(self.bot_name)] if text0.find(self.bot_name) > 0 else text0
        if text0 == '/me':
            n = 5
            if len(text.split()) > 1 and text.split()[1].isdigit():
                n = int(text.split()[1])
                if n < 1 or n > 3 or self.users[user.id].stats[n - 1] is None:
                    s = [str(i + 1) + ", " for i in range(3) if self.users[user.id].stats[i] is not None]
                    s = "".join(s).strip(", ")
                    if not s:
                        bot.sendMessage(chat_id=chat_id, text="У вас ещё нет сохранений")
                    else:
                        bot.sendMessage(chat_id=chat_id, text="Доступны сохранения " + s)
                    return
            self.stat(bot, user.id, chat_id, n)
        elif text0 == '/change':
            n = 4
            player = self.users[user.id]
            if len(text.split()) > 1 and text.split()[1].isdigit():
                n = int(text.split()[1])
                if n < 1 or n > 3 or player.stats[n - 1] is None:
                    s = [str(i + 1) + ", " for i in range(3) if player.stats[i] is not None]
                    s = "".join(s).strip(", ")
                    if not s:
                        bot.sendMessage(chat_id=chat_id, text="У вас ещё нет сохранений")
                    else:
                        bot.sendMessage(chat_id=chat_id, text="Доступны сохранения " + s)
                    return
            if player.stats[n - 1] is None:
                bot.sendMessage(chat_id=chat_id, text="Пришлёшь мне ещё один форвард твоих статов?")
                return
            self.change(bot, user.id, chat_id, n)
        elif text0 == '/stat':
            name = ""
            try:
                name = text.split()[1].strip("@").lower()
            except ImportError:
                bot.sendMessage(chat_id=chat_id, text="А чьи статы-то?")
                return
            if name not in self.usersbyname.keys():
                # print(name)
                bot.sendMessage(chat_id=chat_id, text="Кто это вообще такой? Я его не знаю...")
                return
            if (user.id not in self.admins) and (
                            user.id not in self.masters.keys() or self.users[self.usersbyname[name]].squad not in
                        self.masters[
                            user.id]):
                bot.sendMessage(chat_id=chat_id, text="Любопытство не порок\nНо меру то знать надо...")
                return
            self.stat(bot, self.usersbyname[name], chat_id, 5)
        elif text0[:-1] == '/save' and 1 <= int(text0[-1]) <= 3:
            player = self.users[user.id]
            ps = player.get_stats(4)
            player.set_stats(cur, ps, int(text0[-1]) - 1)
            conn.commit()
            bot.sendMessage(chat_id=chat_id, text="Текущая статистика сохранена в ячейку №" + text0[-1])
        elif text0 == '/top':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ALL, time=message.date)
        elif text0 == '/rushtop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ATTACK, time=message.date)
        elif text0 == '/hptop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.HP, time=message.date)
        elif text0 == '/acctop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ACCURACY, time=message.date)
        elif text0 == '/agtop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.AGILITY, time=message.date)
        elif text0 == '/ortop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ORATORY, time=message.date)
        elif text0 == '/raidtop':
            self.top(bot, user.id, user.username, chat_id, text, StatType.RAIDS, time=message.date)
        elif text0 == '/players':
            self.top(bot, user.id, user.username, chat_id, text, StatType.ALL, invisible=True, title="Игроки",
                     time=message.date)
        elif text0 == "/new_squad" and (user.id in self.admins) and (
                        message.chat.type == "group" or message.chat.type == "supergroup"):
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@").lower()
            if master not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + master)
                return
            self.add_squad(cur, bot, self.usersbyname[master], short.lower(), message.chat.title, user.id, chat_id)
            conn.commit()
        elif text0 == "/make_master":
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@").lower()
            if master not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + master)
                return
            self.add_master(cur, bot, self.usersbyname[master], user.id, short)
            conn.commit()
        elif text0 == "/add":
            short, player = "", ""
            try:
                short, player = text.split()[1:3]
            except ValueError:
                bot.sendMessage(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            player = player.strip("@").lower()
            short = short.lower()
            if player not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="не знаю пользователя @" + player)
                return
            if short not in self.squadnames.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого отряда")
                return
            if (user.id not in self.admins) and (
                            user.id not in self.masters.keys() or short not in self.masters[user.id]):
                bot.sendMessage(chat_id=chat_id, text="У тебя нет такой власти")
                return
            self.add_to_squad(cur, self.usersbyname[player], short)
            bot.sendMessage(chat_id=chat_id,
                            text=("@" + player + " теперь в отряде <b>" + self.squadnames[short] + "</b>"),
                            parse_mode='HTML')
            conn.commit()
        elif text0 == "/echo":
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for pl in self.users.values():
                    for sq in sqs:
                        if sq is None or sq == pl.squad:
                            try:
                                bot.sendMessage(chat_id=pl.chatid, text=msg)
                            except:
                                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                                text="Пользователь @" + pl.username + " отключил бота")
                            break
            bot.sendMessage(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/echo-s":
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    bot.sendMessage(chat_id=self.squadids[sq], text=msg, reply_markup=telega.ReplyKeyboardRemove())
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/pin":
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    self.pin(bot=bot, chat_id=self.squadids[sq], text=msg, uid=chat_id)
        elif text0 == "/rename":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            if len(text.split()) < 3:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неверный формат")
                return
            pl = text.split()[1].strip("@").lower()
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            text = text + " \n"
            for i in range(2):
                k = min(text.find(" "), text.find("\n"))
                text = text[k + 1:]
            text = text.strip()
            player = self.users[self.usersbyname[pl]]
            player.nic = text
            player.update_text(cur)
            conn.commit()
            bot.sendMessage(chat_id=self.users[user.id].chatid,
                            text="Пользователя @" + player.username + " теперь зовут <b>" + player.nic + "</b>",
                            parse_mode='HTML')
            return
        elif text0 == "/ban":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            if len(text.split()) != 2:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неверный формат")
                return
            pl = text.split()[1].strip("@").lower()
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            self.ban(cur, self.usersbyname[pl])
            bot.sendMessage(chat_id=chat_id, text="Вы его больше не увидите")
            conn.commit()
        elif text0 == "/kick":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            if len(text.split()) != 2:
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неверный формат")
                return
            pl = text.split()[1].strip("@").lower()
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            self.ban(cur, self.usersbyname[pl], False)
            bot.sendMessage(chat_id=chat_id, text="Я выкинул его из списков")
            conn.commit()
        elif text0 == "/expel":
            pl = text.split()[1].strip("@").lower()
            if pl not in self.usersbyname.keys():
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Не знаю такого")
                return
            player = self.users[self.usersbyname[pl]]
            if (user.id not in self.admins) and (
                    user.id not in self.masters.keys() and player.squad not in self.masters[
                user.id]):
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Сомневаюсь что ваших полномочий на это хватит...")
                return
            self.del_from_squad(cur, player.id)
            bot.sendMessage(chat_id=chat_id, text="Больше он не в отряде")
        elif text0 == "/online":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinonline is None:
                self.pinonline = PinOnline(self.squadids, bot)
            for sq in text.split()[1:]:
                self.pinonline.pin(sq, self.users[user.id].chatid)
        elif text0 == "/copyonline":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinonline is None:
                self.pinonline = PinOnline(self.squadids, bot)
            self.pinonline.copy_to(chat_id)
        elif text0 == "/pinonkm":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                self.pinkm = PinOnlineKm(self.squadids, bot)
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    self.pinkm.pin(sq, self.users[user.id].chatid, msg)
        elif text0 == "/closekm":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                return
            self.pinkm.close()
            self.pinkm = None

        elif text0 == "/copykm":
            if user.id not in self.admins:
                bot.sendMessage(chat_id=self.users[user.id].chatid,
                                text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                return
            self.pinkm.copy_to(chat_id)
        elif text0.lower() == "/viva_six":
            if chat_id not in self.viva_six.keys():
                self.viva_six[chat_id] = 0
            if self.viva_six[chat_id] % 2 == 0:
                bot.sendMessage(chat_id=chat_id, text="/VIVA_SIX")
            else:
                bot.sendSticker(chat_id=chat_id, sticker="CAADAgADawAD73zLFo43Bv0UZFkCAg")
            self.viva_six[chat_id] += 1
        elif text0 == "/faq":
            text = "<b>Неплохой FAQ по игре:</b> http://telegra.ph/FAQ-02-13-3\n"
            bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=False)
        elif text0 == "/dungs":
            text = "<b>Гайд по подземельям: </b> http://telegra.ph/Podzemelya-02-13\n"
            bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=False)
        elif text0 == '/squads':
            self.list_squads(bot, chat_id, (user.id in self.admins))
        else:
            if message.chat.type == "private":
                bot.sendMessage(chat_id=self.users[user.id].chatid, text="Неизвестная команда... Сам придумал?")

    def start(self):
        self.updater.start_polling()

    def handle_massage(self, bot, update):
        message = update.message
        chat_id = message.chat_id
        user = message.from_user
        # print("!",  message.chat_id, user.username)
        if user.id in self.blacklist and message.chat.type == "private":
            bot.sendMessage(chat_id=chat_id, text="Прости, но тебе здесь не рады")
            return
        text = message.text.strip(" \n\t")
        conn = None
        cur = None
        try:
            conn = sql.connect(self.database)
            cur = conn.cursor()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        if (message.forward_from is not None) and (message.forward_from.id == 430930191) and (
                        '🗣' in text and '❤️' in text and '🔥' in text and '⚔️' in text) and message.chat.type == "private":
            if user.id not in self.users.keys():
                if "Убежище 6" not in text:
                    bot.sendMessage(chat_id=chat_id, text="А ты фракцией не ошибся?")
                    return
                if message.date - message.forward_date > datetime.timedelta(minutes=2):
                    bot.sendMessage(chat_id=chat_id, text="А можно профиль посвежее?")
                    return
                self.users[user.id] = Player(cur)
                self.users[user.id].id = user.id
                self.users[user.id].chatid = chat_id
                self.usersbyname[user.username.lower()] = user.id
                try:
                    cur.execute("INSERT INTO users(id, chatid, username) VALUES(?, ?, ?)",
                                (user.id, chat_id, user.username))
                    if not self.handle_forward(cur, bot, message):
                        del (self.users[user.id])
                        del (self.usersbyname[user.username])
                        return
                except:
                    del (self.users[user.id])
                    del (self.usersbyname[user.username])
                    return
                conn.commit()
                self.users[user.id].keyboard = KeyboardType.DEFAULT
                bot.sendMessage(chat_id=chat_id, text="Я тебя запомнил",
                                reply_markup=self.keyboards[KeyboardType.DEFAULT])
            elif self.handle_forward(cur, bot, message):
                conn.commit()
            return
        if user.id not in self.users.keys():
            if message.chat.type == "private":
                bot.sendMessage(chat_id=chat_id, text="Мы ещё не знакомы. Скинь мне форвард своих статов))",
                                reply_markup=telega.ReplyKeyboardRemove())
            return
        if text[0] == '/':
            self.handle_command(cur, conn, bot, message)
            if message.chat.type == "private":
                bot.sendMessage(reply_markup=self.keyboards[self.users[user.id].keyboard])
        else:
            player = self.users[user.id]
            if message.chat.type == "private":
                if text == "🔙 Назад":
                    player.keyboard = KeyboardType.DEFAULT
                    bot.sendMessage(chat_id=chat_id, text="Добро пожаловать в <b>главное меню</b>",
                                    reply_markup=self.keyboards[player.keyboard], parse_mode='HTML')
                    return
                if player.keyboard == KeyboardType.DEFAULT:
                    if text == "👻 О боте":
                        self.info(bot, player)
                        return
                    elif text == "👨‍💻 О жизни":
                        self.guide(bot, player, private=True)
                        return
                    elif text == "🎖 Топы":
                        player.keyboard = KeyboardType.TOP
                        bot.sendMessage(chat_id=chat_id,
                                        text="Здесь ты можешь увидеть списки лучших игроков 6 убежища\n"
                                             "<i>* перед именем игрока говорят о том, что его профиль устарел, чем их меньше тем актуальнее данные</i>",
                                        reply_markup=self.keyboards[player.keyboard], parse_mode='HTML')
                        return
                    elif text == "💽 Моя статистика":
                        player.keyboard = KeyboardType.STATS
                        bot.sendMessage(chat_id=chat_id,
                                        text="Здесь ты можешь посмотреть свои статы, сохранить их или посмотреть прирост",
                                        reply_markup=self.keyboards[player.keyboard], parse_mode='HTML')
                        return
                elif player.keyboard == KeyboardType.TOP:
                    s = ""
                    ctext = ""
                    if text == "🏅 Рейтинг":
                        ctext = "top"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.ALL, time=message.date,
                                     textmode=True)
                    elif text == "⚔️ Дамагеры":
                        ctext = "rushtop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.ATTACK, time=message.date,
                                     textmode=True)
                    elif text == "❤️ Танки":
                        ctext = "hptop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.HP, time=message.date,
                                     textmode=True)
                    elif text == "🤸🏽‍♂️ Ловкачи":
                        ctext = "agtop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.AGILITY, time=message.date,
                                     textmode=True)
                    elif text == "🔫 Снайперы":
                        ctext = "acctop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.ACCURACY, time=message.date,
                                     textmode=True)
                    elif text == "🗣 Дипломаты":
                        ctext = "ortop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.ORATORY, time=message.date,
                                     textmode=True)
                    elif text == "🔪 Рейдеры":
                        ctext = "raidtop"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.RAIDS, time=message.date,
                                     textmode=True)
                    elif text == "📜 Полный список":
                        ctext = "players"
                        s = self.top(bot, user.id, user.username, chat_id, "", StatType.ALL, invisible=True,
                                     title="Игроки", time=message.date, textmode=True)
                    if s != "":
                        markup = self.top_markup(user, ctext)
                        if markup != []:
                            bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML', disable_web_page_preview=True,
                                            reply_markup=telega.InlineKeyboardMarkup(markup))
                        else:
                            bot.sendMessage(chat_id=chat_id, text=s, parse_mode='HTML', disable_web_page_preview=True,
                                            reply_markup=None)
                        return
                elif player.keyboard == KeyboardType.STATS:
                    if text == '📱 Статистика':
                        self.my_stat(bot, player, 5)
                        return
                    elif text == '🔝 Прирост':
                        self.my_change(bot, player, 4)
                        return
                    elif text == '📲 Сохранить':
                        markup = [telega.InlineKeyboardButton(text=str(i), callback_data="save " + str(i)) for i in
                                  range(1, 4)]
                        bot.sendMessage(chat_id=chat_id, text="Выбери ячейку для сохранения💾", parse_mode='HTML',
                                        disable_web_page_preview=True,
                                        reply_markup=telega.InlineKeyboardMarkup([markup]))
                        return
                bot.sendMessage(chat_id=chat_id, text="Это что-то странное🤔\nДумать об этом я конечно не буду 😝",
                                reply_markup=self.keyboards[player.keyboard])

    def top_markup(self, user, ctext, name=""):
        sq = set()
        plaeyer = self.users[user.id]
        if user.id in self.admins:
            sq = set(v for v in self.squadids.keys())
        elif user.id in self.masters.keys():
            sq = self.masters[user.id]
        if plaeyer.squad:
            sq.add(plaeyer.squad)
        markup = []
        if len(sq) > 0:
            t0 = "Все ⚙️Убежище 6"
            if name == "":
                t0 += " ✔️"
            markup.append([telega.InlineKeyboardButton(text=t0, callback_data=ctext)])
            for q in sq:
                t0 = ""
                if name == q:
                    t0 = " ✔️"
                markup.append(
                    [telega.InlineKeyboardButton(text=self.squadnames[q] + t0, callback_data=str(ctext + " " + q))])
        return markup

    def info(self, bot, player: Player):
        text = "Перед вами стат бот 6 убежища <i>и он крут😎</i>\nОзнакомиться с его командами вы можете по ссылке" \
               " http://telegra.ph/StatBot-Redizajn-09-30\nНо для вашего же удобства рекомендую пользоваться графическим интерфейсом\n" \
               "Бот создан во имя блага и процветания 6 убежища игроком @ant_ant\n" \
               "Так что если найдете в нем серьезные баги - пишите мне)\nЕсли есть желание помочь - можете подкинуть" \
               " денег (https://qiwi.me/67f1c4c8-705c-4bb3-a8d3-a35717f63858) на поддержку бота или связаться со мной и записаться в группу альфа-тестеров\n" \
               "\n<i>Играйте, общайтесь, радуйтесь жизни! Вместе мы сильнейшая фракция в игре!</i>\n\n<i>P.S.: Бот продолжает развиваться. Дальше будет лучше</i>"
        bot.sendMessage(chat_id=player.chatid, text=text, parse_mode='HTML', disable_web_page_preview=True,
                        reply_markup=self.keyboards[player.keyboard])

    def guide(self, bot, player: Player, chat_id = None, private=False):
        text =  "<b>Неплохой FAQ по игре:</b> http://telegra.ph/FAQ-02-13-3\n"\
                "<b>Гайд по подземельям: </b> http://telegra.ph/Podzemelya-02-13\n"
        if chat_id is None:
            chat_id = player.chatid
        if private:
            text += "<i>Автор гайдов</i> @vladvertov"
            bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True,
                            reply_markup=self.keyboards[player.keyboard])
        else:
            bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=False,
                        reply_markup=telega.ReplyKeyboardRemove())

    def statchange_markup(self, n, text, player: Player):
        buttons = ["1", "2", "3", "Прошлый", "Текущий"]
        if text == "change":
            buttons = buttons[:-1]
        buttons[n] += " ✔️"
        f = []
        for i in range(3):
            if player.stats[i] is not None:
                f.append(telega.InlineKeyboardButton(text=buttons[i], callback_data=text + " " + str(i)))
        l = []
        for i in range(3, len(buttons)):
            if player.stats[i] is not None:
                l.append(telega.InlineKeyboardButton(text=buttons[i], callback_data=text + " " + str(i)))
        res = []
        if f != []:
            res.append(f)
        if l != []:
            res.append(l)
        return res

    def my_stat(self, bot, player: Player, n, id=None):
        s = self.stat(bot, player.id, player.chatid, n, textmode=True)
        markup = self.statchange_markup(n - 1, "stat", player)
        if markup != []:
            markup = telega.InlineKeyboardMarkup(markup)
        else:
            markup = None
        if id is None:
            bot.sendMessage(chat_id=player.chatid, text=s, parse_mode='HTML', disable_web_page_preview=True,
                            reply_markup=markup)
        else:
            bot.editMessageText(chat_id=player.chatid, message_id=id, text=s, parse_mode='HTML',
                                disable_web_page_preview=True, reply_markup=markup)

    def my_change(self, bot, player: Player, n, id=None):
        s = self.change(bot, player.id, player.chatid, n, textmode=True)
        markup = self.statchange_markup(n - 1, "change", player)
        if markup != []:
            markup = telega.InlineKeyboardMarkup(markup)
        else:
            markup = None
        if id is None:
            bot.sendMessage(chat_id=player.chatid, text=s, parse_mode='HTML', disable_web_page_preview=True,
                            reply_markup=markup)
        else:
            bot.editMessageText(chat_id=player.chatid, message_id=id, text=s, parse_mode='HTML',
                                disable_web_page_preview=True, reply_markup=markup)

    def handle_callback(self, bot: telega.Bot, update: telega.Update):
        query = update.callback_query
        message = query.message
        chat_id = message.chat_id
        user = query.from_user
        if user.id in self.kick.keys() and datetime.datetime.now() - self.kick[user.id] < datetime.timedelta(
                milliseconds=500):
            bot.answer_callback_query(callback_query_id=query.id, text="Wow Wow Wow полегче")
            return
        self.kick[user.id] = datetime.datetime.now()
        data = query.data
        if data == "":
            return
        conn = None
        cur = None
        try:
            conn = sql.connect(self.database)
            cur = conn.cursor()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        text = data.split()[0]
        name = ""
        try:
            name = data.split()[1]
        except:
            pass
        player = self.users[user.id]
        s = ""
        if text == "top":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.ALL, time=message.date, textmode=True)
        elif text == "rushtop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.ATTACK, time=message.date, textmode=True)
        elif text == "hptop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.HP, time=message.date, textmode=True)
        elif text == "agtop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.AGILITY, time=message.date, textmode=True)
        elif text == "acctop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.ACCURACY, time=message.date,
                         textmode=True)
        elif text == "ortop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.ORATORY, time=message.date, textmode=True)
        elif text == "raidtop":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.RAIDS, time=message.date, textmode=True)
        elif text == "players":
            s = self.top(bot, user.id, user.username, chat_id, data, StatType.ALL, invisible=True, title="Игроки",
                         time=message.date, textmode=True)
        elif text == "stat":
            self.my_stat(bot, self.users[user.id], int(name) + 1, message.message_id)
        elif text == "change":
            self.my_change(bot, self.users[user.id], int(name) + 1, message.message_id)
        elif text == "save":
            n = int(name)
            if n < 1 or n > 3:
                bot.answer_callback_query(callback_query_id=query.id, text="что-то не так")
                return
            ps = player.get_stats(4)
            player.set_stats(cur, ps, n - 1)
            conn.commit()
            s = "Текущая статистика сохранена в ячейку №" + str(n)
        elif text == "online":
            if not self.pinonline.add(player, chat_id):
                self.pinonline.delete(player)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        elif text == "offline":
            self.pinonline.close()
            self.pinonline = None
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        elif text == "onkm":
            if not self.pinkm.add(player, chat_id, name):
                self.pinkm.delete(player)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        elif text == "offkm":
            self.pinkm.close()
            self.pinkm = None
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        if s != "":
            markup = []
            if "top" in text or "players" in text:
                markup = self.top_markup(user, text, name)
            if markup != []:
                bot.editMessageText(chat_id=chat_id, message_id=message.message_id, text=s, parse_mode='HTML',
                                    disable_web_page_preview=True,
                                    reply_markup=telega.InlineKeyboardMarkup(markup))
            else:
                bot.editMessageText(chat_id=chat_id, message_id=message.message_id, text=s, parse_mode='HTML',
                                    disable_web_page_preview=True, reply_markup=None)
        bot.answer_callback_query(callback_query_id=query.id, text="Готово")


if __name__ == "__main__":
    f = open("bot.txt")
    db, tk, name = [s.strip() for s in f.readline().split()]
    bot = Bot(db, tk, name)
    bot.start()
    print("admins:", bot.admins)
    print("squadnames:", bot.squadnames.keys())
    print("users", bot.usersbyname.keys())

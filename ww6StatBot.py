#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = "0.0.0"

from telegram.ext import Updater
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import CommandHandler
from telegram.ext import CallbackQueryHandler
import telegram as telega
import sqlite3 as sql
import datetime
import time
import re
import yaml
import logging
import sys
from enum import Enum
from ww6StatBotPin import PinOnlineKm
from ww6StatBotUtils import send_split, pin, MessageManager, Timer
from ww6StatBotPlayer import Player, PlayerStat, PlayerSettings
from ww6StatBotEvents import Notificator
import ww6StatBotParser as parser


class StatType(Enum):
    ALL = 1
    ATTACK = 2
    HP = 3
    ACCURACY = 4
    AGILITY = 5
    ORATORY = 6
    RAIDS = 7


class Bot:
    CONFIG_PATH = 'bot.yml'

    def __init__(self):
        self.configure()
        conn = None
        try:
            conn = sql.connect(self.db_path)
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
        self.usersbyname = {}
        self.masters = {}
        self.users = {}
        self.squadnames = {}
        self.squadids = {}
        self.squads_by_id = {}
        self.kick = {}
        self.viva_six = {}
        self.apm = {}
        self.keyboards = {}
        self.keyboards[Player.KeyboardType.DEFAULT] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("💽 Моя статистика"),
              telega.KeyboardButton("🎖 Топы")],
             [telega.KeyboardButton("👻 О боте"),
              telega.KeyboardButton("👨‍💻 О жизни")],
             [telega.KeyboardButton("🔧 Настройки")]],
            resize_keyboard=True)
        self.keyboards[Player.KeyboardType.TOP] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("🏅 Рейтинг"), telega.KeyboardButton("⚔️ Дамагеры"),
              telega.KeyboardButton("❤️ Танки")],
             [telega.KeyboardButton("🤸🏽‍♂️ Ловкачи"), telega.KeyboardButton("🔫 Снайперы"),
              telega.KeyboardButton("🗣 Дипломаты")],
             [telega.KeyboardButton("🔪 Рейдеры"), telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        self.keyboards[Player.KeyboardType.STATS] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("📱 Статистика"), telega.KeyboardButton("🔝 Прирост")],
             [telega.KeyboardButton("📲 Сохранить"), telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        self.keyboards[Player.KeyboardType.SETTINGS] = telega.ReplyKeyboardMarkup(
            [[telega.KeyboardButton("👫 Сменить пол"), telega.KeyboardButton("⏰ Напоминания")],
             [telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
        self.state = Player.KeyboardType.DEFAULT
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
            self.squads_by_id[r[2]] = r[1].lower()
        cur.close()

        self.updater = Updater(token=self.tg_token)
        self.timer = Timer()
        self.message_manager = MessageManager(self.updater.bot, timer=self.timer)
        self.pinkm = PinOnlineKm(self.squadids, self.users, self.message_manager, self.db_path,
                                 timer=self.timer, conn=conn)
        self._parser = parser.Parser(self.message_manager)
        if not self.pinkm.is_active:
            self.pinkm.close()
            self.pinkm = None

        self.notificator = None
        if len(self.users) > 0:
            self.notificator = Notificator(self.users, self.updater.bot)

        massage_handler = MessageHandler(Filters.text | Filters.command, self.handle_massage)
        start_handler = CommandHandler('start', self.handle_start)
        callback_handler = CallbackQueryHandler(callback=self.handle_callback)
        join_handler = MessageHandler(Filters.status_update.new_chat_members, self.handle_new_members)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(massage_handler)
        self.updater.dispatcher.add_handler(join_handler)
        self.updater.dispatcher.add_handler(callback_handler)
        self.updater.start_polling(clean=True)

        print("admins:", self.admins)
        print("squadnames:", self.squadnames.keys())
        print("users", self.usersbyname.keys())
        self.updater.idle()

    def configure(self):
        f = open(self.CONFIG_PATH)
        if not f:
            raise Exception('missed config file %s. check example at bot.yml.dist' % self.CONFIG_PATH)
        c = yaml.load(f)

        mandatory_opts = {
            'db': ['path'],
            'tg': ['token', 'bot_name'],
            'ratelimit': ['report_chat_id']
        }

        for section, opts in mandatory_opts.items():
            if section not in c:
                raise Exception('%s: missed mandatory section %s' % (self.CONFIG_PATH, section))
            cfg_opts = c[section]
            for opt in opts:
                if opt not in cfg_opts:
                    raise Exception(
                        '%s: missed mandatory option %s in the section %s' % (self.CONFIG_PATH, opt, section))
                setattr(self, '_'.join([section, opt]), cfg_opts[opt])

    def handle_start(self, bot, update):
        message = update.message
        user = message.from_user
        if message.chat.type != "private":
            return
        if user.id in self.blacklist:
            self.message_manager.send_message(chat_id=message.chat_id, text="Не особо рад тебя видеть.\nУходи",
                                              reply_markup=telega.ReplyKeyboardRemove())
            return
        elif user.id not in self.users.keys():
            self.message_manager.send_message(chat_id=message.chat_id,
                                              text="Привет, давай знакомиться.\nКидай мне форвард своих статов",
                                              reply_markup=telega.ReplyKeyboardRemove())
            return
        self.users[user.id].keyboard = Player.KeyboardType.DEFAULT
        self.message_manager.send_message(chat_id=message.chat_id, text="Рад тебя видеть",
                                          reply_markup=self.keyboards[Player.KeyboardType.DEFAULT])

    def update_apm(self, uid, bot):
        if uid not in self.apm.keys():
            self.apm[uid] = set()
        now = datetime.datetime.now()
        self.apm[uid].add(now)
        tmp = self.apm[uid].copy()
        for t in tmp:
            if now - t > datetime.timedelta(seconds=70):
                self.apm[uid].remove(t)
        if len(self.apm[uid]) > 15:
            self.message_manager.send_message(chat_id=self.users[uid].chatid, text="не спами")
        if len(self.apm[uid]) > 20:
            self.message_manager.send_message(chat_id=self.ratelimit_report_chat_id,
                                              text="Игрок @" + self.users[uid].username + " спамит")

    def add_admin(self, id):
        conn = sql.connect(self.db_path)
        if not id in self.admins:
            cur = conn.cursor()
            cur.execute("INSERT INTO admins(id) VALUES (?)", (id,))
            self.admins.add(id)
            conn.commit()

    def del_admin(self, id):
        conn = sql.connect(self.db_path)
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

    def unban(self, cur, id):
        if id in self.blacklist:
            cur.execute("DELETE FROM blacklist WHERE id=?", (id,))
            self.blacklist.remove(id)
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
        if sq not in self.squadnames.keys():
            self.message_manager.send_message(chat_id=self.users[adminid].chatid, text="Нет такого отряда")
            return False
        if (adminid not in self.admins) and ((adminid not in self.masters.keys()) or (sq not in self.masters[adminid])):
            self.message_manager.send_message(chat_id=self.users[adminid].chatid,
                                              text="У вас нет на это прав. Возьмите их у Антона")
            return False
        if (id in self.masters.keys()) and sq in self.masters[id]:
            self.message_manager.send_message(chat_id=self.users[adminid].chatid, text="Да он и так командир)")
            return False
        cur.execute("INSERT INTO masters(id, name) VALUES (?, ?)", (id, sq))
        if id not in self.masters.keys():
            self.masters[id] = [sq]
        else:
            self.masters[id].add(sq)
        return True

    def del_master(self, cur, bot, id, adminid):
        if adminid not in self.admins:
            self.message_manager.send_message(chat_id=self.users[adminid].chatid,
                                              text="У вас нет на это прав.\nНи малейших")
            return False
        if id in self.masters.keys():
            del (self.masters[id])
            cur.execute("DELETE FROM masters WHERE id = ?", (id,))
            return True
        return False

    def add_squad(self, cur, bot, master, short, title, id, chat_id):
        if id not in self.admins:
            self.message_manager.send_message(chat_id=self.users[id].chatid,
                                              text="Хм... А кто тебе сказал что ты так можешь?")
            return
        if master not in self.users.keys():
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Пользователь @" + master + " ещё не зарегестрирован")
            return
        if (short in self.squadnames.keys()) or short == "none":
            self.message_manager.send_message(chat_id=chat_id, text="Краткое имя \"" + short + "\" уже занято")
            return
        r = (title, short, chat_id)
        cur.execute("INSERT INTO squads(name, short, chatid) VALUES(?, ?, ?)", r)
        self.masters[master] = set()
        self.squadnames[short] = r[0]
        self.squadids[short] = r[2]
        self.squads_by_id[chat_id] = short
        self.add_master(cur, bot, master, id, short)
        self.message_manager.send_message(chat_id=chat_id,
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
            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML')

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
            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML')

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
        nosquad = True
        cap = False
        admin = id in self.admins
        if text != "" and len(text.split()) != 1:
            sq = text.split()[1].lower()
            cap = id in self.masters.keys() and sq in self.masters[id]
            if self.users[id].squad != sq and not cap and not admin:
                self.message_manager.send_message(chat_id=chat_id, text="Похоже, это не ваш отряд", parse_mode='HTML')
                return
            if sq in self.squadnames.keys():
                nosquad = False
                s = s[:-5] + "</b> отряда <b>" + self.squadnames[sq] + ":</b>"
        i = 1
        sum = 0
        for val, name, nic, squad, lasttime in arr:
            lasttime = str(lasttime)
            lasttime = datetime.datetime.strptime(lasttime.split('.')[0], "%Y-%m-%d %H:%M:%S")
            if nosquad or squad == sq:
                if (id in self.admins) or i <= 5 or ((not nosquad) and cap) or invisible or name == username:
                    if (id in self.admins) or ((not nosquad) and cap):
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
                if textmode and i == 101:
                    break
        if (id in self.admins or ((not nosquad) and cap)) and not invisible:
            s += "\n\nОбщий счет: " + str(sum)
        if not textmode:
            N = 50
            if invisible:
                N = 100
            send_split(bot, s, chat_id, N)
        else:
            return s

    def who_is(self, bot, chat_id, text):
        m = re.match(r'[\S]+[\s]+(?P<name>.+)', text)
        if not m:
            self.message_manager.send_message(chat_id=chat_id, text="Неверный формат\nПопробуй еще раз)")
            return
        name = m.group('name').strip().lower()
        res = []
        l = len(name)
        for pl in self.users.values():
            if (name in pl.nic.lower()) and (len(pl.nic) < 2 * l):
                res.append((len(pl.nic), pl.nic, pl.username))
        if not res:
            self.message_manager.send_message(chat_id=chat_id, text="Я таких не знаю\n¯\_(ツ)_/¯")
            return
        res.sort()
        res = ['@{} - {}'.format(u[2], u[1]) for u in res]
        self.message_manager.send_message(chat_id=chat_id, text=("Игроки с похожим ником:\n{1}".format(
            name, '\n'.join(res))), parse_mode='HTML')

    def list_squads(self, bot, chat_id, show_pin=False):
        text = ""
        for sqshort, sqname in self.squadnames.items():
            text += "<b>" + sqname + "</b> aka <i>" + sqshort + "</i>"
            if show_pin:
                if self.pinkm and sqshort in self.pinkm.chat_messages.keys():
                    text += " \t✅"
                else:
                    text += " \t❌"
            text += "\n"
        self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True)

    def _err_callback(self, e: telega.TelegramError, args):
        call_back_chat, pl = args
        if call_back_chat and "bot was blocked by the user" in e.message:
            self.message_manager.send_message(chat_id=call_back_chat,
                                              text="Игрок @{} заблокировал меня((".format(pl.username))

    def echo(self, bot: telega.Bot, message, call_back_chat=None, squads=None, status: PinOnlineKm.PlayerStatus = None):
        """squads should be iterable, no rights are checked"""
        for pl in self.users.values():
            if (not squads or pl.squad in squads) and \
                    (status is None or (self.pinkm and self.pinkm.player_status(pl) == status)):
                self.message_manager.send_message(chat_id=pl.chatid, callback=self._err_callback,
                                                  callbackargs=(call_back_chat, pl),
                                                  text=message)

    def demand_squads(self, text, user, bot, allow_empty=False):
        if len(text.split()) <= 1:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="сообщения-то и нехватает")
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
            if not allow_empty:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Весело наверное писать в несуществующий отряд")
            return [], text[start:]
        if user.id not in self.admins and user.id not in self.masters.keys() and not all(sq in self.masters[
            user.id] for sq in sqs):
            self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                              text="Небеса не одарили тебя столь великой властью\nМожешь рискнуть обратиться за "
                                                   "ней к Антону")
            return None, None
        if not text[start:]:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Но что же мне им написать?")
            return None, None
        return sqs, text[start:]

    def no_permission(self, user, sq):
        return (user.id not in self.admins) and (user.id not in self.masters.keys() or sq not in self.masters[user.id])

    def demand_ids(self, message: telega.Message, user, offset=1, all=False, allow_empty=False, limit=None):
        """не проверяет на права администратора
        может вернуть пустую строку"""
        # TODO all, limit and allow_empty combination is not intuitive
        text = message.text
        if len(text.split()) < offset or len(text.split()) == offset and not message.reply_to_message:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Чего-то здесь не хватает")
            return None, None
        ids = []
        start = -1
        split = text.split()
        i = 0
        for word in split[offset:]:
            name = word.strip('@').lower()
            if name in self.usersbyname.keys():
                ids.append(self.usersbyname[name])
            elif not all:
                start = text.find(word)
                break
            else:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Не знаю игрока по имени @" + name)
            i += 1
            if limit and i >= limit:
                break
        if not ids and message.reply_to_message and message.reply_to_message.from_user:
            uid, name = message.reply_to_message.from_user.id, message.reply_to_message.from_user.username
            if uid in self.users.keys():
                ids.append(uid)
            else:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Не знаю игрока по имени @" + name)
        if not ids and not allow_empty:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                              text="Я не нашёл ни одного знакомого юзернейма")
        return text[start:], ids

    def who_spy(self, bot, chat_id, user, msg):
        _, ids = self.demand_ids(msg, user, offset=2, all=True)
        text = msg.text
        if not ids:
            return
        sq = text.split()[1]
        if sq not in self.squadids.keys():
            self.message_manager.send_message(chat_id=chat_id, text='Нет такого отряда')
            return
        if self.no_permission(user, sq):
            self.message_manager.send_message(chat_id=chat_id, text='Ты явно права не имеешь...')
            return
        freeusr = []
        difsq = []
        average = []
        for uid in ids:
            pl = self.users[uid]
            days = (datetime.datetime.now() - datetime.datetime.strptime(str(pl.stats[4].time).split('.')[0],
                                                                         "%Y-%m-%d %H:%M:%S")).days
            if pl.squad == '':
                freeusr.append('@{0} (<b>{1}</b>)'.format(pl.username, pl.nic))
            elif pl.squad == sq:
                average.append('@{0} (<b>{1}</b>)-\t<b>{2}</b>'.format(pl.username, pl.nic, str(days)))
            else:
                difsq.append('@{0} (<b>{1}</b>) - <b>{2}</b>'.format(pl.username, pl.nic, self.squadnames[pl.squad]))
        res = ""
        if freeusr:
            res += 'Свободные игроки:\n\t' + '\n\t'.join(freeusr) + '\n\t'
        if difsq:
            res += 'Игроки из других отрядов:\n\t' + '\n\t'.join(difsq) + '\n\t'
        if average:
            res += 'Игроки из этого отряда:\n\t' + '\n\t'.join(average) + '\n\t'
            self.message_manager.send_message(chat_id=chat_id, text=res, parse_mode='HTML')

    def handle_post(self, bot: telega.Bot, message: telega.Message):
        chat_from = message.chat
        if chat_from.username and chat_from.username.lower() == 'greatwar':
            for squad in self.squadids.values():
                try:
                    bot.forward_message(chat_id=squad, from_chat_id=chat_from.id, message_id=message.message_id)
                except:
                    pass

    def handle_command(self, cur, conn, bot, message):
        text = message.text
        user = message.from_user
        chat_id = message.chat_id
        text0 = text[:text.find(' ')] if text.find(' ') > 0 else text
        text0 = text0[:text0.find(self.tg_bot_name)] if text0.find(self.tg_bot_name) > 0 else text0
        if text0 == '/me':
            n = 5
            if len(text.split()) > 1 and text.split()[1].isdigit():
                n = int(text.split()[1])
                if n < 1 or n > 3 or self.users[user.id].stats[n - 1] is None:
                    s = [str(i + 1) + ", " for i in range(3) if self.users[user.id].stats[i] is not None]
                    s = "".join(s).strip(", ")
                    if not s:
                        self.message_manager.send_message(chat_id=chat_id, text="У вас ещё нет сохранений")
                    else:
                        self.message_manager.send_message(chat_id=chat_id, text="Доступны сохранения " + s)
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
                        self.message_manager.send_message(chat_id=chat_id, text="У вас ещё нет сохранений")
                    else:
                        self.message_manager.send_message(chat_id=chat_id, text="Доступны сохранения " + s)
                    return
            if player.stats[n - 1] is None:
                self.message_manager.send_message(chat_id=chat_id, text="Пришлёшь мне ещё один форвард твоих статов?")
                return
            self.change(bot, user.id, chat_id, n)
        elif text0 == '/stat':
            _, ids = self.demand_ids(message, user=user, all=True)
            for uid in ids:
                if self.no_permission(user, self.users[uid].squad):
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text="Любопытство не порок\nНо меру то знать надо...\nСтатистика @"
                                                           + self.users[uid].username + " тебе не доступна")
                    return
                self.stat(bot, uid, chat_id, 5)
        elif text0 == '/look_up':
            _, ids = self.demand_ids(message, user=user, all=True, offset=2)
            N = 5
            if ids:
                N = int(text.split()[1])
            else:
                return
            for uid in ids:
                if self.no_permission(user, self.users[uid].squad):
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text="Любопытство не порок\nНо меру то знать надо...\nСтатистика @"
                                                           + self.users[uid].username + " тебе не доступна")
                    return
                self.stat(bot, uid, chat_id, N)
        elif text0 == '/check_up':
            _, ids = self.demand_ids(message, user=user, all=True, offset=2)
            N = 5
            if ids:
                N = int(text.split()[1])
            else:
                return
            for uid in ids:
                if self.no_permission(user, self.users[uid].squad):
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text="Любопытство не порок\nНо меру то знать надо...\nСтатистика @"
                                                           + self.users[uid].username + " тебе не доступна")
                    return
                self.change(bot, uid, chat_id, N)
        elif text0[:-1] == '/save' and 1 <= int(text0[-1]) <= 3:
            player = self.users[user.id]
            ps = player.get_stats(4)
            player.set_stats(cur, ps, int(text0[-1]) - 1)
            conn.commit()
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Текущая статистика сохранена в ячейку №" + text0[-1])
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
        # elif text0 == '/players':
        #    self.top(bot, user.id, user.username, chat_id, text, StatType.ALL, invisible=True, title="Игроки",
        #             time=message.date)
        elif text0 == "/new_squad" and (user.id in self.admins) and (
                message.chat.type == "group" or message.chat.type == "supergroup"):
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                self.message_manager.send_message(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@").lower()
            if master not in self.usersbyname.keys():
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="не знаю пользователя @" + master)
                return
            self.add_squad(cur, bot, self.usersbyname[master], short.lower(), message.chat.title, user.id, chat_id)
            conn.commit()
        elif text0 == "/make_master":
            short, master = "", ""
            try:
                short, master = text.split()[1:3]
            except ValueError:
                self.message_manager.send_message(id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            master = master.strip("@").lower()
            if master not in self.usersbyname.keys():
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="не знаю пользователя @" + master)
                return
            if self.add_master(cur, bot, self.usersbyname[master], user.id, short):
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Теперь @" + master + " командир <b>" + short + "</b>",
                                                  parse_mode='HTML')
            conn.commit()
        elif text0 == '/disgrace':
            _, ids = self.demand_ids(message, user=user, all=True)
            for uid in ids:
                if self.del_master(cur, bot, uid, user.id):
                    self.message_manager.send_message(chat_id=chat_id, text="Больше он не командир\nИ вообще никто")
            conn.commit()
        elif text0 == "/add":
            _, ids = self.demand_ids(message, user=user, all=True, offset=2)
            short = ""
            if ids:
                short = text.split()[1]
            else:
                return
            for uid in ids:
                if (user.id not in self.admins) and ((user.id not in self.masters.keys() or
                                                      short not in self.masters[user.id]) or
                                                     (self.users[uid].squad != "" and self.users[uid].squad != short)):
                    self.message_manager.send_message(chat_id=chat_id, text="У тебя нет такой власти")
                    return
                self.add_to_squad(cur, uid, short)
                self.message_manager.send_message(chat_id=chat_id,
                                                  text=("@" + self.users[uid].username + " теперь в отряде <b>" +
                                                        self.squadnames[
                                                            short] + "</b>"),
                                                  parse_mode='HTML')
            conn.commit()
        elif re.match("/echo_(?P<type>[\S]+)([\s]|$)|/echo([\s]|$)", text0):
            type = re.match("/echo_(?P<type>[\S]+)([\s]|$)|/echo([\s]|$)", text0).group('type')
            if type:
                type = type.strip()
            status = None  # TODO consider using dict instead
            if type is None:
                pass
            elif type == 'lost':
                status = PinOnlineKm.PlayerStatus.UNKNOWN
            elif type == 'going':
                status = PinOnlineKm.PlayerStatus.GOING
            elif type == 'scared':
                status = PinOnlineKm.PlayerStatus.SCARED
            elif type == 'skipping':
                status = PinOnlineKm.PlayerStatus.SKIPPING
            elif type == 'raiding':
                status = PinOnlineKm.PlayerStatus.ONPLACE
            else:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Нет такого /echo")
                return
            sqs, msg = self.demand_squads(text, user, bot, allow_empty=True)
            if sqs is None:
                return
            if not sqs and user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Ты не одмен, тебе не можно")
                return
            if not msg:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="А писать-то и нечего")
                return
            self.echo(bot, msg, self.users[user.id].chatid, sqs, status)
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/echo-s":
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    self.message_manager.send_message(chat_id=self.squadids[sq], text=msg,
                                                      reply_markup=telega.ReplyKeyboardRemove())
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif text0 == "/pin":
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    pin(bot=bot, chat_id=self.squadids[sq], text=msg, uid=chat_id)
        elif text0 == "/rename":
            m = re.search(r'\S+\s+@?(?P<username>\S+)\s+(?P<name>.+)', text)
            if (not m):
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            pl = m.group('username').lower()
            if pl not in self.usersbyname.keys():
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Пользователь @" + pl + " мне не извесен")
                return
            player = self.users[self.usersbyname[pl]]
            sq = player.squad
            if self.no_permission(user, sq):
                self.message_manager.send_message(chat_id=chat_id, text="Твоих прав на это не хватит\nТочно знаю")
                return
            player.nic = m.group('name')
            player.update_text(cur)
            conn.commit()
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Пользователя @" + player.username + " теперь зовут <b>" + player.nic + "</b>",
                                              parse_mode='HTML')
            return
        elif text0 == "/ban":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            _, ids = self.demand_ids(message, user=user, all=True)
            if not ids:
                return
            for uid in ids:
                self.ban(cur, uid)
                self.message_manager.send_message(chat_id=chat_id, text="Я выкинул его из списков")
            conn.commit()
        elif text0 == '/unban':
            m = re.match(r'^[\S]+[\s]+(?P<id>[\d]+)', text)
            if not m:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            uid = int(m.group('id'))
            if self.unban(cur, uid):
                self.message_manager.send_message(chat_id=chat_id, text="Разбанил")
                conn.commit()
            else:
                self.message_manager.send_message(chat_id=chat_id, text="Да и не был он в бане")
        elif text0 == "/remove":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Великая сила - это великая ответственность\nРазве ты настолько ответственен?")
                return
            _, ids = self.demand_ids(message, user=user, all=True)
            if not ids:
                return
            for uid in ids:
                self.ban(cur, uid, False)
                self.message_manager.send_message(chat_id=chat_id, text="Я выкинул его из списков")
            conn.commit()
        elif text0 == "/expel":
            _, ids = self.demand_ids(message, user=user, all=True)
            if not ids:
                return
            for uid in ids:
                pl = self.users[uid]
                if self.no_permission(user, pl.squad):
                    self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                      text="Ты не властен над @" + pl.username)
                    return
                self.del_from_squad(cur, pl.id)
                self.message_manager.send_message(chat_id=chat_id, text="Больше @" + pl.username + " не в отряде")
            conn.commit()
        elif text0 == "/kick":
            _, ids = self.demand_ids(message, user=user, all=True, offset=2)
            if not ids:
                return
            sq = text.split()[1]
            if self.no_permission(user, sq):
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Ты не властен над этим отрядом")
                return
            for uid in ids:
                pl = self.users[uid]
                if pl.squad == sq:
                    self.del_from_squad(cur, pl.id)
                    self.message_manager.send_message(chat_id=chat_id, text="Больше @" + pl.username + " не в отряде")
                try:
                    self.message_manager.bot.kick_chat_member(chat_id=self.squadids[sq], user_id=uid,
                                                              until_date=datetime.datetime.now() + datetime.timedelta(
                                                                  seconds=40))
                except:
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text="Выкинуть @" + pl.username + " из чата не получилось")
            conn.commit()
        elif text0 == "/pinonkm":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                self.pinkm = PinOnlineKm(self.squadids, self.users, self.message_manager, self.db_path,
                                         timer=self.timer)
            sqs, msg = self.demand_squads(text, user, bot)
            if sqs:
                for sq in sqs:
                    self.pinkm.pin(sq, self.users[user.id], msg)
        elif text0 == "/closekm":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                self.message_manager.send_message(chat_id=chat_id, text="Активных пинов нет")
                return
            self.pinkm.close()
            self.pinkm = None
            self.message_manager.send_message(chat_id=chat_id, text="Пины закрыты")
        elif text0 == "/copykm":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                return
            self.pinkm.copy_to(chat_id)
        elif text0.lower() == "/viva_six":
            if chat_id not in self.viva_six.keys():
                self.viva_six[chat_id] = 0
            if self.viva_six[chat_id] % 2 == 0:
                self.message_manager.send_message(chat_id=chat_id, text="/VIVA_SIX")
            else:
                bot.sendSticker(chat_id=chat_id, sticker="CAADAgADgAAD73zLFnbBnS7BK3KuAg")
            self.viva_six[chat_id] += 1
        elif text0 == "/faq":
            text = "<b>Неплохой FAQ по игре:</b> http://telegra.ph/FAQ-02-13-3\n"
            self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML',
                                              disable_web_page_preview=False)
        elif text0 == "/dungs":
            text = "<b>Гайд по подземельям: </b> http://telegra.ph/Gajd-po-podzemelyam-04-26\n"
            self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML',
                                              disable_web_page_preview=False)
        elif text0 == "/rfm":

            text = "<b>Гайд для новичка: </b> {}\n ".format("telegra.ph/FAQ-po-igre-Wasteland-Wars-04-06-2"
                                                            if self.squads_by_id.get(chat_id) in (
            'ls', 'ld', 'la', 'vd') else
                                                            "telegra.ph/FAQ-po-igre-Wasteland-Wars-04-16")

            self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML',
                                              disable_web_page_preview=False)
        elif text0 == '/squads':
            self.list_squads(bot, chat_id, (user.id in self.admins))
        elif text0 == '/whois':
            self.who_is(bot, chat_id, text)
        elif text0 == '/whospy':
            self.who_spy(bot, chat_id, user, message)
        elif text0 == '/raidson':
            m = re.match(r'^[\S]+[\s]+((?P<g>[\S]+)[\s]+)?(?P<n>[\d]+)', text)
            if not m:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            sq = m.group('g')
            n = int(m.group('n'))
            if sq is None:
                if user.id not in self.admins:
                    self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                      text="Кто ты такой, чтобы просить меня о подобном?")
                    return
            elif self.no_permission(user, sq):
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Недостаточно власти\nНужно больше власти")
                return
            start = str(datetime.datetime.now() - datetime.timedelta(hours=8 * n))
            raids = []
            for pl in self.users.values():
                if sq is None or pl.squad == sq:
                    cur.execute(r'SELECT * FROM raids WHERE id = ? AND time > ?', (pl.id, start))
                    raids.append((len(cur.fetchall()), pl.nic, pl.username))
            raids.sort(reverse=True)
            if sq:
                msg = "Топ рейдеров отряда <b>" + self.squadnames[sq] + "</b>\nНачиная с " + start.split('.')[
                    0] + "\n" + \
                      "\n".join(['{})<a href = "t.me/{}">{}</a> <b>{}</b>'
                                .format(i + 1, raids[i][2], raids[i][1], raids[i][0]) for i in range(len(raids))])
            else:
                msg = "Топ рейдеров\nНачиная с " + start.split('.')[0] + "\n" + \
                      "\n".join(['{})<a href = "t.me/{}">{}</a> <b>{}</b>'
                                .format(i + 1, raids[i][2], raids[i][1], raids[i][0]) for i in range(len(raids))])
            send_split(bot, msg, chat_id, 50)
        elif text0 == '/whoisonraid':
            m = re.match(r'^[\S]+([\s]+(?P<g>[\S]+))?', text)
            if not m:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            sq = m.group('g')
            if sq is None:
                if user.id not in self.admins:
                    self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                      text="Кто ты такой, чтобы просить меня о подобном?")
                    return
            elif self.no_permission(user, sq):
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Недостаточно власти\nНужно больше власти")
                return
            onplace = []
            going = []
            skipping = []
            unknown = []
            scared = []
            if self.pinkm is None:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Я... это...\nПин не нашел")
                return
            for pl in self.users.values():
                if sq is None or pl.squad == sq:
                    if pl.id not in self.pinkm.players_online.keys():
                        unknown.append('@' + pl.username)
                    else:
                        st = self.pinkm.players_online[pl.id]['state']
                        if st == PinOnlineKm.PlayerStatus.SKIPPING:
                            skipping.append('@' + pl.username)
                        elif st == PinOnlineKm.PlayerStatus.GOING:
                            going.append('@' + pl.username)
                        elif st == PinOnlineKm.PlayerStatus.ONPLACE:
                            onplace.append('@' + pl.username)
                        elif st == PinOnlineKm.PlayerStatus.SCARED:
                            scared.append('@' + pl.username)
            msg = "Уже на точке:\n\t{}\nЕщё в пути:\n\t{}\nНе могут ходить так далеко:\n\t{}\nНе соизволили пойти:\n\t{}\nПропали без вести:\n\t{}".format(
                "\n\t".join(onplace), "\n\t".join(going), "\n\t".join(scared), "\n\t".join(skipping),
                "\n\t".join(unknown)
            )
            if sq:
                msg = "В отряде <b>" + self.squadnames[sq] + "</b>\n" + msg
            send_split(bot, msg, chat_id, 100)
        elif text0 == '/autoping':
            m = re.match(r'^[\S]+([\s]+(?P<g>[\S]+))?', text)
            if not m:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Неверный формат команды")
                return
            sq = m.group('g')
            if sq is None:
                self.message_manager.send_message(chat_id=chat_id, text="Нехватает отряда")
                return
            if self.no_permission(user, sq):
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Хмм... чего-то не хватает...\nА!  Точно! Твоих прав")
                return
            if self.pinkm is None:
                self.message_manager.send_message(chat_id=chat_id, text="Пина нету")
                return
            list_to_ping = []
            self.message_manager.send_message(chat_id=self.squadids[sq], text="Пин видели? А он вас нет...")
            for pl in self.users.values():
                if pl.squad == sq and self.pinkm.player_status(pl) == PinOnlineKm.PlayerStatus.UNKNOWN:
                    list_to_ping.append('@' + pl.username)
                    if len(list_to_ping) == 3:
                        self.message_manager.send_message(chat_id=self.squadids[sq], text=" ".join(list_to_ping))
                        list_to_ping.clear()
            if list_to_ping:
                self.message_manager.send_message(chat_id=self.squadids[sq], text=" ".join(list_to_ping))
        elif text0 == '/info':
            _, ids = self.demand_ids(message, user, all=True, allow_empty=True)
            if not ids:
                return
            for uid in ids:
                pl = self.users[uid]
                sq = "из отряда <b>{}</b>".format(
                    self.squadnames[pl.squad]) if pl.squad in self.squadnames.keys() else ""
                text = "Это <b>{0}</b> {1}".format(pl.nic, sq)
                self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML',
                                                  disable_web_page_preview=True)
        elif text0 == '/when_raid':
            now = datetime.datetime.now()
            raid_h = ((int(now.hour) + 7) // 8) * 8 + 1
            d = 0 if raid_h < 24 else 1
            raid_h %= 24
            sec = int((datetime.datetime(year=now.year, month=now.month, day=now.day, hour=raid_h)
                       + datetime.timedelta(days=d) - datetime.datetime.now()).total_seconds())
            h = sec // 3600
            m = (sec % 3600) // 60
            sec %= 60
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Ближайший рейд в <b>{}:00</b> мск\nТ.е. через <b>{}</b> ч <b>{}</b> мин <b>{}</b> сек"
                                              .format(raid_h, h, m, sec), parse_mode="HTML")
        else:
            if message.chat.type == "private":
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Неизвестная команда... Сам придумал?")

    def start(self):
        self.updater.start_polling()

    def handle_massage(self, bot, update: telega.Update):
        if update.channel_post:
            self.handle_post(bot, update.channel_post)
            return
        message = update.message
        chat_id = message.chat_id
        user = message.from_user
        # print("!",  message.chat_id, user.username)
        if user.id in self.blacklist and message.chat.type == "private":
            self.message_manager.send_message(chat_id=chat_id, text="Прости, но тебе здесь не рады")
            return
        text = message.text.strip(" \n\t")
        conn = None
        cur = None
        try:
            conn = sql.connect(self.db_path)
            cur = conn.cursor()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])
        parse_result = self._parser.run(message)
        if parse_result.stats is not None and message.chat.type == "private":
            if user.id not in self.users.keys():
                if parse_result.fraction != "⚙️Убежище 6":
                    self.message_manager.send_message(chat_id=chat_id, text="А ты фракцией не ошибся?")
                    return
                if parse_result.timedelta > datetime.timedelta(minutes=2):
                    self.message_manager.send_message(chat_id=chat_id, text="А можно профиль посвежее?")
                    return
                self.users[user.id] = Player(cur)
                self.users[user.id].id = user.id
                self.users[user.id].chatid = chat_id
                try:
                    cur.execute("INSERT INTO users(id, chatid, username) VALUES(?, ?, ?)",
                                (user.id, chat_id, user.username))
                except:
                    del (self.users[user.id])
                    del (self.usersbyname[user.username])
                    return
                conn.commit()
                self.users[user.id].keyboard = Player.KeyboardType.DEFAULT
                self.message_manager.send_message(chat_id=chat_id, text="Я тебя запомнил",
                                                  reply_markup=self.keyboards[Player.KeyboardType.DEFAULT])

            player = self.users[user.id]
            player.username = parse_result.username
            self.usersbyname[parse_result.username.lower()] = user.id
            player.update_text(cur)
            if player.nic == "" or parse_result.timedelta < datetime.timedelta(seconds=15):
                player.nic = parse_result.nic
            elif player.nic != parse_result.nic:
                self.message_manager.send_message(chat_id=player.chatid,
                                                  text="🤔 Раньше ты играл под другим ником.\nМожешь отправить <b>свежий</b> профиль?\n"
                                                       "Если ты сменил игровой ник и у тебя лапки обратись к @ant_ant или своему командиру\n"
                                                       "<code>А иначе не кидай мне чужой профиль!</code>",
                                                  parse_mode='HTML')
                player.update_text(cur)
                conn.commit()
                return
            player.update_text(cur)

            oldps = player.get_stats(4)
            ps = parse_result.stats
            ps.raids = 0
            if oldps is not None:
                player.set_stats(cur, oldps, 3)
                ps.raids = oldps.raids
            date = parse_result.raid_time
            # TODO make raid incrementation separated from stat update
            if date and ((user.id, date) not in self.raids):
                self.raids.add((user.id, date))
                ps.raids += 1
                ps.update_raids(cur, user.id, date)
                if player.squad in self.squadnames.keys():
                    personal = " отличился на рейде " if player.settings.sex != "female" else " отличилась на рейде "
                    text = "<b>" + player.nic + "</b> aka @" + player.username + personal + parse_result.raid_text
                    text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    call = lambda e, ca: self.message_manager.send_message(chat_id=player.chatid,
                                                                           text="Я не смог отправить сообщение в твой отряд\nЕсли хочешь - отправь его сам:\n\n" + text,
                                                                           parse_mode='HTML')
                    self.message_manager.send_message(callback=call, chat_id=self.squadids[player.squad], text=text,
                                                      parse_mode='HTML')
                self.message_manager.send_message(chat_id=player.chatid, text="Засчитан успешный рейд",
                                                  parse_mode='HTML')
            player.set_stats(cur, ps, 4)
            player.update_text(cur)
            self.message_manager.send_message(chat_id=player.chatid, text="Я занес твои результаты")
            conn.commit()
            return

        if user.id not in self.users.keys():
            if message.chat.type == "private":
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Мы ещё не знакомы. Скинь мне форвард своих статов))",
                                                  reply_markup=telega.ReplyKeyboardRemove())
            return
        if text[0] == '/':
            self.handle_command(cur, conn, bot, message)
            if message.chat.type == "private":
                self.message_manager.send_message(reply_markup=self.keyboards[self.users[user.id].keyboard])
        else:
            player = self.users[user.id]
            if message.chat.type == "private":
                if text == "🔙 Назад":
                    player.keyboard = Player.KeyboardType.DEFAULT
                    self.message_manager.send_message(chat_id=chat_id, text="Добро пожаловать в <b>главное меню</b>",
                                                      reply_markup=self.keyboards[player.keyboard], parse_mode='HTML')
                    return
                if player.keyboard == Player.KeyboardType.DEFAULT:
                    if text == "👻 О боте":
                        self.info(bot, player)
                        return
                    elif text == "👨‍💻 О жизни":
                        self.guide(bot, player)
                        return
                    elif text == "🎖 Топы":
                        player.keyboard = Player.KeyboardType.TOP
                        self.message_manager.send_message(chat_id=chat_id,
                                                          text="Здесь ты можешь увидеть списки лучших игроков 6 убежища\n"
                                                               "<i>* перед именем игрока говорят о том, что его профиль устарел, чем их меньше тем актуальнее данные</i>",
                                                          reply_markup=self.keyboards[player.keyboard],
                                                          parse_mode='HTML')
                        return
                    elif text == "💽 Моя статистика":
                        player.keyboard = Player.KeyboardType.STATS
                        self.message_manager.send_message(chat_id=chat_id,
                                                          text="Здесь ты можешь посмотреть свои статы, сохранить их или посмотреть прирост",
                                                          reply_markup=self.keyboards[player.keyboard],
                                                          parse_mode='HTML')
                        return
                    elif text == '🔧 Настройки':
                        player.keyboard = Player.KeyboardType.SETTINGS
                        self.message_manager.send_message(chat_id=chat_id,
                                                          text="Здесь ты можешь изменить личные настройки",
                                                          reply_markup=self.keyboards[player.keyboard],
                                                          parse_mode='HTML')
                        return
                elif player.keyboard == Player.KeyboardType.TOP:
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
                    # elif text == "📜 Полный список":
                    #    ctext = "players"
                    #    s = self.top(bot, user.id, user.username, chat_id, "", StatType.ALL, invisible=True,
                    #                 title="Игроки", time=message.date, textmode=True)
                    if s != "":
                        markup = self.top_markup(user, ctext)
                        if markup != []:
                            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML',
                                                              disable_web_page_preview=True,
                                                              reply_markup=telega.InlineKeyboardMarkup(markup))
                        else:
                            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML',
                                                              disable_web_page_preview=True,
                                                              reply_markup=None)
                        return
                elif player.keyboard == Player.KeyboardType.STATS:
                    if text == '📱 Статистика':
                        self.my_stat(bot, player, 5)
                        return
                    elif text == '🔝 Прирост':
                        self.my_change(bot, player, 4)
                        return
                    elif text == '📲 Сохранить':
                        markup = [telega.InlineKeyboardButton(text=str(i), callback_data="save " + str(i)) for i in
                                  range(1, 4)]
                        self.message_manager.send_message(chat_id=chat_id, text="Выбери ячейку для сохранения💾",
                                                          parse_mode='HTML',
                                                          disable_web_page_preview=True,
                                                          reply_markup=telega.InlineKeyboardMarkup([markup]))
                        return
                elif player.keyboard == Player.KeyboardType.SETTINGS:
                    msg = ""
                    if text == "👫 Сменить пол":
                        if player.settings.sex == "male":
                            player.settings.sex = "female"
                            msg = "Пол изменен на <b>женский</b>"
                        else:
                            player.settings.sex = "male"
                            msg = "Пол изменен на <b>мужской</b>"
                        player.settings.update(cur)
                        conn.commit()
                        self.message_manager.send_message(text=msg, chat_id=chat_id, parse_mode="HTML")
                        return
                    elif text == "⏰ Напоминания":
                        markup = self.notifications_markup(player)
                        self.message_manager.send_message(chat_id=chat_id, text="Выбери время напоминаний",
                                                          reply_markup=telega.InlineKeyboardMarkup(markup))
                        return
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Это что-то странное🤔\nДумать об этом я конечно не буду 😝",
                                                  reply_markup=self.keyboards[player.keyboard])

    def info(self, bot, player: Player):
        text = "Перед вами стат бот 6 убежища <i>и он крут😎</i>\nОзнакомиться с его командами вы можете по ссылке" \
               " http://telegra.ph/StatBot-Redizajn-09-30\nНо для вашего же удобства рекомендую пользоваться графическим интерфейсом\n" \
               "Бот создан во имя блага и процветания 6 убежища игроком @ant_ant\n" \
               "Так что если найдете в нем серьезные баги - пишите мне)\nЕсли есть желание помочь - можете подкинуть" \
               " денег (https://qiwi.me/67f1c4c8-705c-4bb3-a8d3-a35717f63858) на поддержку бота или связаться со мной и записаться в группу альфа-тестеров\n" \
               "\n<i>Играйте, общайтесь, радуйтесь жизни! Вместе мы сильнейшая фракция в игре!</i>\n\n<i>P.S.: Бот продолжает развиваться. Дальше будет лучше</i>"
        self.message_manager.send_message(chat_id=player.chatid, text=text, parse_mode='HTML',
                                          disable_web_page_preview=True,
                                          reply_markup=self.keyboards[player.keyboard])

    def guide(self, bot, player: Player, chat_id=None):
        text = "<b>FAQ по игре:</b> http://telegra.ph/FAQ-02-13-3\nОт @vladvertov\n\n" \
               "<b>Гайд по подземельям: </b> http://telegra.ph/Gajd-po-podzemelyam-04-26\n" \
               "От @Rey_wolf и @ICallThePolice\n\n<b>Гайд для новичка </b> " \
               "http://telegra.ph/gajd-dlya-novichkov-po-Wastelands-18-ot-Quapiam-and-co-03-17\nОт @Quapiam"
        if chat_id is None:
            chat_id = player.chatid
        self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True,
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

    def notifications_markup(self, player: Player):
        buttons = ["B {}{}".format(x, " ✅" if player.settings.notifications[x] else "")
                   for x in player.settings.notif_time]
        text = "notif"
        res = []
        for i in range(0, len(player.settings.notif_time), 3):
            line = []
            for j in range(3):
                if i + j < len(player.settings.notif_time):
                    line.append(telega.InlineKeyboardButton(text=buttons[i + j], callback_data=text + " " + str(i + j)))
            res.append(line)
        return res

    def my_stat(self, bot, player: Player, n, id=None):
        s = self.stat(bot, player.id, player.chatid, n, textmode=True)
        markup = self.statchange_markup(n - 1, "stat", player)
        if markup != []:
            markup = telega.InlineKeyboardMarkup(markup)
        else:
            markup = None
        if id is None:
            self.message_manager.send_message(chat_id=player.chatid, text=s, parse_mode='HTML',
                                              disable_web_page_preview=True,
                                              reply_markup=markup)
        else:
            self.message_manager.update_msg(chat_id=player.chatid, message_id=id, text=s, parse_mode='HTML',
                                            disable_web_page_preview=True, reply_markup=markup)

    def my_change(self, bot, player: Player, n, id=None):
        s = self.change(bot, player.id, player.chatid, n, textmode=True)
        markup = self.statchange_markup(n - 1, "change", player)
        if markup != []:
            markup = telega.InlineKeyboardMarkup(markup)
        else:
            markup = None
        if id is None:
            self.message_manager.send_message(chat_id=player.chatid, text=s, parse_mode='HTML',
                                              disable_web_page_preview=True,
                                              reply_markup=markup)
        else:
            self.message_manager.update_msg(chat_id=player.chatid, message_id=id, text=s, parse_mode='HTML',
                                            disable_web_page_preview=True, reply_markup=markup)

    def handle_new_members(self, bot, update: telega.Update):
        users = update.message.new_chat_members
        chat_id = update.message.chat_id
        if self.squads_by_id.get(chat_id) not in ('v6', 'ld', 'a6'):
            return
        time.sleep(2)
        for user in users:
            text = "Рад тебя видеть, <b>{}</b>".format(self.users[user.id].nic) if user.id in self.users.keys() else \
                "Привет, @{}! Давай знакомиться! Я бот-статистик этого убежища.\nГо в личку)".format(user.username)
            self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML')

    def handle_callback(self, bot: telega.Bot, update: telega.Update):
        query = update.callback_query
        message = query.message
        chat_id = message.chat_id
        user = query.from_user
        if user.id not in self.users.keys():
            bot.answer_callback_query(callback_query_id=query.id, text="Мы еще не знакомы, го в лс")
            return
        self.update_apm(user.id, bot)
        if user.id in self.kick.keys() and datetime.datetime.now() - self.kick[user.id] < datetime.timedelta(
                milliseconds=700):
            bot.answer_callback_query(callback_query_id=query.id, text="Wow Wow Wow полегче")
            return
        self.kick[user.id] = datetime.datetime.now()
        data = query.data
        if data == "":
            return
        conn = None
        cur = None
        try:
            conn = sql.connect(self.db_path)
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
        elif text == "onkm":
            if not self.pinkm:
                bot.answer_callback_query(callback_query_id=query.id, text="Этот пин не активен")
                return
            if not self.pinkm.add(player.id, name, self.squads_by_id[chat_id]):
                self.pinkm.delete(player.id, self.squads_by_id[chat_id])
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        elif text == "offkm":
            self.pinkm.close()
            self.pinkm = None
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            return
        elif text == "notif":
            conn = sql.connect(self.db_path)
            cur = conn.cursor()
            i = int(name)
            player.settings.notifications[player.settings.notif_time[i]] = not player.settings.notifications[
                player.settings.notif_time[i]]
            player.settings.update(cur)
            conn.commit()
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
            markup = self.notifications_markup(player)
            s = "Выбери время напоминаний"
            bot.editMessageText(chat_id=message.chat_id, message_id=message.message_id, text=s, parse_mode='HTML',
                                disable_web_page_preview=True, reply_markup=telega.InlineKeyboardMarkup(markup))
            return
        elif text == "going_pin":
            if not self.pinkm:
                bot.answer_callback_query(callback_query_id=query.id, text="Этот пин не активен")
                return
            self.pinkm.change_status(user.id, self.squads_by_id[chat_id], PinOnlineKm.PlayerStatus.GOING)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
        elif text == "skipping_pin":
            if not self.pinkm:
                bot.answer_callback_query(callback_query_id=query.id, text="Этот пин не активен")
                return
            self.pinkm.change_status(user.id, self.squads_by_id[chat_id], PinOnlineKm.PlayerStatus.SKIPPING)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
        elif text == "scared_pin":
            if not self.pinkm:
                bot.answer_callback_query(callback_query_id=query.id, text="Этот пин не активен")
                return
            self.pinkm.change_status(user.id, self.squads_by_id[chat_id], PinOnlineKm.PlayerStatus.SCARED)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
        elif text == "onplace_pin":
            if not self.pinkm:
                bot.answer_callback_query(callback_query_id=query.id, text="Этот пин не активен")
                return
            self.pinkm.change_status(user.id, self.squads_by_id[chat_id], PinOnlineKm.PlayerStatus.ONPLACE)
            bot.answer_callback_query(callback_query_id=query.id, text="Done")
        if s != "":
            markup = []
            if "top" in text or "players" in text:
                markup = self.top_markup(user, text, name)
            if markup != []:
                self.message_manager.update_msg(chat_id=chat_id, message_id=message.message_id, text=s,
                                                parse_mode='HTML',
                                                disable_web_page_preview=True,
                                                reply_markup=telega.InlineKeyboardMarkup(markup))
            else:
                self.message_manager.update_msg(chat_id=chat_id, message_id=message.message_id, text=s,
                                                parse_mode='HTML',
                                                disable_web_page_preview=True, reply_markup=None)
        bot.answer_callback_query(callback_query_id=query.id, text="Готово")


def set_stderr_debug_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


if __name__ == "__main__":
    # set_stderr_debug_logger()

    stat_bot = Bot()
    stat_bot.start()

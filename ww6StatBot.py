#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = "0.0.0"

import datetime
import logging
import os
import re
import sqlite3 as sql
import sys
import time
import warnings
from enum import Enum

import telegram as telega
import yaml
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, Updater)

import ww6StatBotParser as parser
from ww6StatBotEvents import Notificator
from ww6StatBotPin import PinOnlineKm
from ww6StatBotPlayer import Player, PlayerSettings, PlayerStat
from ww6StatBotUtils import MessageManager, Timer


class EnemyMeeting:
    def __init__(self):
        self.fraction = None
        self.nic = None
        self.time = None
        self.distance = None

class StatType(Enum):
    ALL = 1
    ATTACK = 2
    HP = 3
    ACCURACY = 4
    AGILITY = 5
    ORATORY = 6
    RAIDS = 7
    BUILD = 8


class Bot:
    CONFIG_PATH = 'bot.yml'
    MEET_REPORT_CHAT = -1001250232822

    # Define dynamic config variables to avois pylint E1101 error
    # ('Instance of Bot has no ... member')
    db_path = ''
    tg_token = ''
    tg_bot_name = ''
    ratelimit_report_chat_id = ''

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
        cur.execute('CREATE TABLE IF NOT EXISTS building (id INTEGER, time TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS msg_null (id INTEGER, time TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS points (id INTEGER, time TEXT, type TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS blacklist (id INTEGER)')
        cur.execute('CREATE TABLE IF NOT EXISTS titles (user_id INTEGER, titles_json TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS triggers (trigger TEXT, chat TEXT, text TEXT)')
        cur.execute(
            'CREATE TABLE IF NOT EXISTS settings (id REFERENCES users(id) ON DELETE CASCADE, sex TEXT, keyboard INT, raidnotes INT)')
        cur.execute('CREATE TABLE IF NOT EXISTS state (data TEXT)')  # not The best solution ever but it will do
        cur.execute("SELECT * FROM admins")
        self.admins = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM blacklist")
        self.blacklist = set(r[0] for r in cur.fetchall())
        cur.execute("SELECT * FROM raids")
        self.raids = set((r[0], r[1]) for r in cur.fetchall())
        cur.execute("SELECT * FROM building")
        self.building = set((r[0], r[1]) for r in cur.fetchall())
        cur.execute("SELECT * FROM msg_null")  # TODO in refactoring - merge buildig with msg_null and specify msg_type as third argumebt
        self._msg_null = set((r[0], r[1]) for r in cur.fetchall())
        self.usersbyname = {}
        self.masters = {}
        self.users = {}
        self.squadnames = {}
        self.squadids = {}
        self.squads_by_id = {}
        self.kick = {}
        self.viva_six = {}
        self.meetings = {}
        self.apm = {}
        self.apm_window = 0
        self.keyboards = {}
        self.triggers = {'all': {}}
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
             [telega.KeyboardButton("🔪 Рейдеры"), telega.KeyboardButton("🔨 Исследователи"),
              telega.KeyboardButton("🔙 Назад")]], resize_keyboard=True)
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
        cur.execute("SELECT * FROM triggers")
        for r in cur.fetchall():
            tr, sq, tx = r
            if sq not in self.triggers.keys():
                self.triggers[sq] = {}
            self.triggers[sq][tr] = tx
        cur.close()

        self.updater = Updater(
            token=self.tg_token, request_kwargs=self.tg_request_kwargs)
        self.timer = Timer()
        self.message_manager = MessageManager(self.updater.bot, timer=self.timer)
        self.pinkm = PinOnlineKm(self.squadids, self.users, self.message_manager, self.db_path,
                                 timer=self.timer, conn=conn)
        self._parser = parser.Parser(self.message_manager, self.tg_bot_name)
        if not self.pinkm.is_active:
            self.pinkm.close()
            self.pinkm = None

        self.notificator = None
        if len(self.users) > 0:
            self.notificator = Notificator(self.users, self.updater.bot)

        massage_handler = MessageHandler(Filters.text | Filters.command, self.handle_massage)
        photo_handler = MessageHandler(Filters.photo, self.handle_photo)
        start_handler = CommandHandler('start', self.handle_start)
        callback_handler = CallbackQueryHandler(callback=self.handle_callback)
        join_handler = MessageHandler(Filters.status_update.new_chat_members, self.handle_new_members)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(massage_handler)
        self.updater.dispatcher.add_handler(photo_handler)
        self.updater.dispatcher.add_handler(join_handler)
        self.updater.dispatcher.add_handler(callback_handler)

        print("admins:", self.admins)
        print("squadnames:", self.squadnames.keys())
        print("users", self.usersbyname.keys())

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

        # Proxy support
        self.tg_use_proxy = False
        self.tg_request_kwargs = {}
        if 'proxy' in c:
            proxy_config = c['proxy']

            self.tg_use_proxy = True
            self.tg_request_kwargs = {
                'proxy_url': proxy_config['url'],
                'urllib3_proxy_kwargs': {
                    'username': proxy_config['username'],
                    'password': proxy_config['password']
                }
            }
        f.close()

    def save_point(self, msg:telega.Message, point_type, cur: sql.Cursor, conn: sql.Connection):
        if not msg.forward_from:
            return False
        res = (msg.from_user.id, msg.forward_date.isoformat(' ', 'seconds'), point_type)
        self._msg_null.add(res)
        cur.execute('INSERT into points(id, time, type) values(?, ?, ?)', res)
        conn.commit()
        return True

    def null_msg(self, msg:telega.Message, cur: sql.Cursor, conn: sql.Connection):
        if not msg.forward_from:
            return False
        res = (msg.from_user.id, msg.forward_date.isoformat(' ', 'seconds'))
        if res in self._msg_null:
            return False
        self._msg_null.add(res)
        cur.execute('INSERT into msg_null(id, time) values(?, ?)', res)
        conn.commit()
        return True

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

    def update_apm(self, uid):
        if self.timer.ticks * self.timer.interval > self.apm_window * 60:
            self.apm_window = self.timer.ticks * self.timer.interval // 60 + 1
            self.apm.clear()
        if uid not in self.apm.keys():
            self.apm[uid] = 1
        else:
            self.apm[uid] += 1
        if self.apm[uid] > 20:
            self.message_manager.send_message(chat_id=uid, text="не бей по кнопкам - отвалятся")
        if self.apm[uid] > 30:
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

    def add_master(self, cur, id, adminid, sq):
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
            self.masters[id] = set()
        self.masters[id].add(sq)
        return True

    def del_master(self, cur, id, adminid):
        if adminid not in self.admins:
            self.message_manager.send_message(chat_id=self.users[adminid].chatid,
                                              text="У вас нет на это прав.\nНи малейших")
            return False
        if id in self.masters.keys():
            del (self.masters[id])
            cur.execute("DELETE FROM masters WHERE id = ?", (id,))
            return True
        return False

    def add_squad(self, cur, master, short, title, id, chat_id):
        if id not in self.admins:
            self.message_manager.send_message(chat_id=self.users[id].chatid,
                                              text="Хм... А кто тебе сказал что ты так можешь?")
            return
        if master not in self.users.keys():
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Пользователь @" + master + " ещё не зарегестрирован")
            return
        if (short in self.squadnames.keys()) or short in ("none", "all"):
            self.message_manager.send_message(chat_id=chat_id, text="Краткое имя \"" + short + "\" уже занято")
            return
        r = (title, short, chat_id)
        cur.execute("INSERT INTO squads(name, short, chatid) VALUES(?, ?, ?)", r)
        self.masters[master] = set()
        self.squadnames[short] = r[0]
        self.squadids[short] = r[2]
        self.squads_by_id[chat_id] = short
        self.add_master(cur, master, id, short)
        self.message_manager.send_message(chat_id=chat_id,
                                          text="Создан отряд " + self.squadnames[short] + " aka " + short)

    def trigger(self, trigger, chat):
        sq = self.squads_by_id.get(chat)
        text = ""
        trigger = trigger.lower()
        if sq and sq in self.triggers.keys() and trigger in self.triggers[sq].keys():
            text = self.triggers[sq][trigger]
        elif trigger in self.triggers['all'].keys():
            text = self.triggers['all'][trigger]
        if text:
            self.message_manager.send_message(chat_id=chat, text=text, parse_mode="HTML")
        return text

    def add_trigger(self, argument, cur:sql.Cursor):
        m = re.match(r'/(?P<trigger>[\S]+)[\s]+(?P<all>(?P<sq>[\S]+)[\s]*(?P<text>.*))', argument, re.DOTALL)
        if m:
            tg = m.group('trigger').lower()
            all = m.group('all')
            sq = m.group('sq')
            text = m.group('text')

            if sq in self.squadids.keys():
                if self.triggers.get(sq) and self.triggers[sq].get(tg):
                    cur.execute('update triggers SET text=? WHERE chat=? AND trigger=?', (text, sq, tg))
                else:
                    cur.execute('INSERT into triggers(trigger, chat, text) VALUES(?, ?, ?)', (tg, sq, text))
                if sq not in self.triggers.keys():
                    self.triggers[sq] = {}
                self.triggers[sq][tg] = text
                return tg, text
            sq = 'all'
            text = all
            if self.triggers.get(sq) and self.triggers[sq].get(tg):
                cur.execute('update triggers SET text=? WHERE chat=? AND trigger=?', (text, sq, tg))
            else:
                cur.execute('INSERT into triggers(trigger, chat, text) VALUES(?, ?, ?)', (tg, sq, text))
            self.triggers['all'][tg] = all
            return tg, all
        return None

    def del_trigger(self, argument, cur:sql.Cursor):
        m = re.match(r'/(?P<trigger>[\S]+)', argument, re.DOTALL)
        if m:
            tg = m.group('trigger')
            for sq, dic in self.triggers.items():
                if dic.get(tg):
                    del(dic[tg])
                    cur.execute('DELETE from triggers WHERE chat=? AND trigger=?', (sq, tg))
            return tg
        return None

    def stat(self, id, chat_id, n, textmode=False):
        player = self.users[id]
        ps = player.get_stats(n - 1)
        s = "<b>" + player.nic + "</b>\n"
        if player.titles:
            s += '\n'.join(['<code>' + tl + '</code>' for tl in player.titles]) + '\n\n'
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
             "<b>\nВыносливость: </b>" + str(ps.stamina) + \
             "<b>\n\nУспешные рейды:     </b>" + str(ps.raids)+ \
             "<b>\nИсследования:          </b>" + str(ps.building)
        if textmode:
            return s
        else:
            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML')

    def change(self, id, chat_id, n, textmode=False):
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
        if ps.building - ops.building:
            s += "<b>\n\nИсследования:     </b>" + str(ps.building - ops.building)
        if textmode == True:
            return s
        else:
            self.message_manager.send_message(chat_id=chat_id, text=s, parse_mode='HTML')

    def top(self, id, username, chat_id, text, type: StatType, invisible=False, title="",
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
        elif type == StatType.BUILD:
            if not s:
                s = "<b>Топ исследователей:</b>"
            arr = [(pl.get_stats(4).building, pl.username, pl.nic, pl.squad, pl.stats[4].time) for pl in
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
                            id in self.admins or name == username or type in (StatType.ALL, StatType.RAIDS, StatType.BUILD)):
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
            self.message_manager.send_split(s, chat_id, N)
        else:
            return s

    def who_is(self, chat_id, text):
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
            self.message_manager.send_message(chat_id=chat_id, text="Я таких не знаю\n¯\\_(ツ)_/¯")
            return
        res.sort()
        res = ['@{} - {}'.format(u[2], u[1]) for u in res]
        self.message_manager.send_message(
            chat_id=chat_id,
            text="Игроки с похожим ником:\n{}".format('\n'.join(res)),
            parse_mode='HTML')

    def list_squads(self, chat_id, show_pin=False):
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
        block_list, pl = args
        if "bot was blocked by the user" in e.message:
            block_list.append(pl.username)



    def echo(self, message, call_back_chat, squads=None, status: PinOnlineKm.PlayerStatus = None):
        """squads should be iterable, no rights are checked"""
        block_list = []
        for pl in self.users.values():
            if (not squads or pl.squad in squads) and \
                    (status is None or (self.pinkm and self.pinkm.player_status(pl) == status)):
                self.message_manager.send_message(chat_id=pl.chatid, callback=self._err_callback,
                                                  callbackargs=(block_list, pl),
                                                  text=message)

        self.message_manager.send_message(chat_id=call_back_chat, text="Ваш зов был услышан").result()
        if block_list:
            self.message_manager.send_message(chat_id=call_back_chat, text="Меня заблокировали:\n%s"
                                                                           % "".join(['\n@' + val for val in block_list]))

    def demand_squads(self, text: str, user: telega.User, allow_empty_squads=False, default_message: str=""):
        '''
        Splits telegram message text to squad list and message text
        Checks user permissions
        '''
        if len(text.split()) <= 1:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Сообщения-то и не хватает!")
            return None, None

        # Find squad names in message text
        split = text.split()
        sqs = []
        start = -1
        for word in split[1:]:
            if word in self.squadnames.keys():
                sqs.append(word)
            else:
                start = text.find(word)
                break

        if start < 0:
            start = 0

        # Is there any squads?
        if not sqs:
            if not allow_empty_squads:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Весело, наверное, писать в несуществующий отряд?")
                return None, None
            return [], text[start:]

        # Check permissions
        denied = []
        for sq in sqs:
            if not self.user_has_squad_permission(user, sq):
                denied.append(sq)
        if denied:
            if len(denied) == len(sqs):
                message_text = ("Небеса не одарили тебя столь великой властью\n"
                                "Можешь рискнуть обратиться за ней к Антону")
            else:
                message_text = "А ты точно командуешь в {}?".format(", ".join(denied))

            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text=message_text)
            return None, None

        if (not text[start:] or (start == 0)) and not default_message:
            self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Но что же мне им написать?")
            return None, None
        if start == 0:
            return sqs, default_message
        return sqs, text[start:] or default_message

    def user_has_squad_permission(self, user: telega.User, squad: str) -> bool:
        '''
        Checks if user is admin or master for given squad
        '''
        if user.id in self.admins:
            return True
        if user.id in self.masters.keys() and squad in self.masters[user.id]:
            return True
        return False

    def no_permission(self, user, sq):
        '''
        Checks if user has no rights to given squad
        '''
        warnings.warn(
            "no_permission is deprecated, use user_has_squad_permission instead",
            PendingDeprecationWarning
        )
        return not self.user_has_squad_permission(user, sq)

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

    def who_spy(self, chat_id, user, msg):
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
        self.message_manager.send_split(res, chat_id, 50)

    def handle_post(self, message: telega.Message):
        chat_from = message.chat
        if chat_from.username and chat_from.username.lower() == 'greatwar':
            text = self.parse_raid_result(message.date, message.text)
            for squad in self.squadids.values():
                try:
                    self.message_manager.send_message(chat_id=squad, text=text, parse_mode='HTML')
                except:
                    pass
    
    def parse_raid_result(self, raid_datetime, message_text):
        locations = {
            'Старая фабрика': ('📦', 5),
            'Завод "Ядер-Кола"': ('🕳', 9),
            'Тюрьма': ('💊', 12),
            'Склады': ('🍗', 16),
            'Датацентр': ('🔹', 20),
            'Госпиталь': ('❤️', 24),
            'Завод "Электрон"': ('💡', 28),
            'Офисное здание': ('💾', 32),
            'Иридиевая шахта': ('🔩', 38),
            'Склад металла': ('🔗', 46)
        }
        # List of fractions to preserve given order if results equal
        fractions = [
            '⚙️Убежище 6',
            '👨‍🎤Головорезы',
            '⚙️Убежище 4',
            '💣Мегатонна'
        ]

        post_regex = re.compile(r"✅(.+)\nЗаняли (.+)!")
        raid_parse_result = post_regex.findall(message_text)
        raid_result = {fraction: [] for fraction in fractions}
        for location, fraction in raid_parse_result:
            if fraction not in raid_result:
                raid_result[fraction] = []
            if location in locations:
                raid_result[fraction].append('{}{}'.format(*locations[location]))
            else: # in case of new raid locations in game update
                raid_result[fraction].append(location)
        
        # Sort by locations count but preserve given in `fractions` order if location counters are same
        sorter = lambda x: (fractions.index(x[0])/10 if x[0] in fractions else 0) - len(x[1])
        raid_result = sorted(raid_result.items(), key=sorter)

        text = '#итогирейда {} Мск\n\n'.format(raid_datetime.strftime('%d.%m.%Y %H:%M'))
        for fraction, result in raid_result:
            if len(result) > 4:
                result.insert(4, '\n  ')
            text += '<b>{} +{}</b>\n   {}\n'.format(fraction, len(result)*15, ' '.join(result))
        
        return text

    def clear_meetings(self, uid):
        if self.meetings.get(uid):
            del (self.meetings[uid])

    def report_enemy_meeting(self, uid, meet:EnemyMeeting):
        pl = self.users[uid]
        text = 'На <b>{}</b>км замечен <b>{}</b> из <b>{}</b> в {}\nДокладывает <a href="t.me/{}">{}</a>'.format(
            meet.distance, meet.nic, meet.fraction, meet.time.strftime('%H:%M'), pl.username, pl.nic
        )
        self.message_manager.send_message(chat_id=self.MEET_REPORT_CHAT, text=text, parse_mode='HTML',
                                          disable_web_page_preview=True)

    def handle_post_forward(self, update: telega.Update):
        message = update.message
        chat = update.effective_chat
        text = self.parse_raid_result(message.forward_date, message.text)
        self.message_manager.send_message(chat_id=chat.id, text=text, parse_mode='HTML')

    def handle_photo(self, bot, update: telega.Update):
        message = update.message
        chat_id = message.chat_id
        conn = None
        cur = None
        try:
            conn = sql.connect(self.db_path)
            cur = conn.cursor()
        except sql.Error as e:
            print("Sql error occurred:", e.args[0])

        parse = self._parser.run(message)
        if parse.meeting is not None:
            self.handle_meeting(parse, cur, conn)

    def handle_meeting(self, parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if parse.meeting is None or parse.message.chat.type != 'private':
            return
        meet = parse.meeting
        chat_id = parse.message.chat_id
        uid = parse.message.from_user.id
        second_message = False

        if parse.timedelta > datetime.timedelta(minutes=20):
            self.message_manager.send_message(chat_id=chat_id,
                                              text='Я принимаю форварды встреч только за последние 20мин')
            return
        if meet.fraction == '⚙️Убежище 6':
            self.message_manager.send_message(chat_id=chat_id,
                                              text='Рад за вас, но мне интереснее игроки других фракций')
            return
        if meet.nic:
            meeting = EnemyMeeting()
            meeting.nic, meeting.fraction = meet.nic, meet.fraction
            if parse.info_line is not None:  # Maniac
                meeting.distance = parse.info_line.distance
            elif uid in self.meetings.keys():  # second message (with photo)
                last_meet = self.meetings[uid]
                self.clear_meetings(uid)
                if abs(parse.message.forward_date - last_meet.time) > datetime.timedelta(seconds=30):
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text='Сначала пришли сообшение о встречи с километра')
                    return
                meeting.distance = last_meet.distance
                second_message = True
            else:
                self.message_manager.send_message(chat_id=chat_id,
                                                  text='Сначала пришли сообшение о встречи с километра')
                return
            if not self.null_msg(parse.message, cur, conn) and not second_message:
                self.message_manager.send_message(chat_id=chat_id,
                                                  text='Я уже видел этот форвард')
                return
            self.save_point(parse.message, 'MEET', cur, conn)
            meeting.time = parse.message.forward_date
            self.report_enemy_meeting(uid, meeting)
            self.message_manager.send_message(chat_id=chat_id,
                                              text='Спасибо!\nЯ передал, куда нужно😉')
        else:
            if not self.null_msg(parse.message, cur, conn):
                self.message_manager.send_message(chat_id=chat_id,
                                                  text='Я уже видел этот форвард')
                return
            meeting = EnemyMeeting()
            if parse.info_line is None:
                self.message_manager.send_message(chat_id=chat_id, text='Что-то пошло не так')
                return
            meeting.distance = parse.info_line.distance
            meeting.time = parse.message.forward_date
            self.meetings[uid] = meeting
            self.message_manager.send_message(chat_id=chat_id,
                                              text='Спасибо!\nТеперь пришли форвард с фоткой')

    def handle_getto(self, parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if parse.getto is None or parse.message.chat.type != 'private':
            return
        chat_id = parse.message.chat_id
        uid = parse.message.from_user.id
        pl = self.users[uid]
        if not self.null_msg(parse.message, cur, conn):
            self.message_manager.send_message(chat_id=chat_id,
                                              text='Я уже видел этот форвард')
            return
        text = '<a href="t.me/{}">{}</a> докладывает из гетто в {}:\n{}'.format(
            pl.username, pl.nic, parse.message.forward_date.strftime('%H:%M'),
            "\n".join(['<b>{}</b> из <b>{}</b>'.format(x.nic, x.fraction)
                       for x in parse.getto if x.fraction != '⚙️Убежище 6'])
        )
        self.message_manager.send_message(chat_id=self.MEET_REPORT_CHAT, text=text, parse_mode='HTML',
                                          disable_web_page_preview=True)
        self.message_manager.send_message(chat_id=chat_id,
                                          text='Спасибо!\nЯ передал, куда нужно😉')

    def handle_pve(self, parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if not parse.pve or parse.message.chat.type != 'private':
            return
        pve = parse.pve
        uid = parse.message.from_user.id
        pl = self.users[uid]
        chat_id = parse.message.chat_id
        text = ""
        if not self.null_msg(parse.message, cur, conn):
            text = "Я уже видел этот форвард"
        elif parse.timedelta > datetime.timedelta(minutes=2):
            text = "Слишком поздно, у тебя лишь 2 минуты, чтобы отправить мне результаты боя"
        else:
            text = 'PVE <a href="t.me/{}">{}</a> с <b>{}</b>\n{}км\nПолученный урон:{}\n' \
               'Нанесеный урон:{}\nПобеда:{}'.format(pl.username, pl.nic, pve.mob_nic, parse.info_line.distance,
                                                     str(pve.damage_taken),str(pve.damage_dealt),
                                                     'Да' if pve.win else 'Нет')
            if not parse.loot:
                text += '\nНо данжи не принимаются'
            elif pve.win:
                self.save_point(parse.message, 'PVE', cur, conn)
                text += '\nЗасчитан бой'

        self.message_manager.send_message(text=text, chat_id=chat_id, parse_mode='HTML', disable_web_page_preview=True)

    def handle_pvp(self, parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if not parse.pvp or parse.message.chat.type != 'private':
            return
        pvp = parse.pvp
        uid = parse.message.from_user.id
        pl = self.users[uid]
        chat_id = parse.message.chat_id
        text = ""
        if not self.null_msg(parse.message, cur, conn):
            text = "Я уже видел этот форвард"
        elif parse.timedelta > datetime.timedelta(minutes=2):
            text = "Слишком поздно, у тебя лишь 2 минуты, чтобы отправить мне результаты боя"
        else:
            text = 'PVP <b>{0}</b> с <b>{1}</b>\n<b>{0}</b> выбил: {2}\n' \
               '<b>{1}</b> выбил: {3}\n\nПобеда:<b>{4}</b>'.format(pvp.nics[0], pvp.nics[1], str(pvp.dd[pvp.nics[0]]),
                                                                              str(pvp.dd[pvp.nics[1]]), pvp.win)
            if pvp.win == pl.nic:
                self.save_point(parse.message, 'PVP', cur, conn)
                text += '\nЗасчитан бой'

        self.message_manager.send_message(text=text, chat_id=chat_id, parse_mode='HTML', disable_web_page_preview=True)

    def handle_loot(self, parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if not parse.loot or not self.null_msg(parse.message, cur, conn):
            return
        # chat_id = parse.message.chat_id
        # loot = parse.loot
        # text = 'LOOT\n'+'\n'.join(['{}: {}шт'.format(k, v) for k, v in loot.items()])
        # self.message_manager.send_message(text=text, chat_id=chat_id, parse_mode='HTML', disable_web_page_preview=True)

    def handle_loss(self,  parse: parser.ParseResult, cur: sql.Cursor, conn: sql.Connection):
        if not parse.loss or not self.null_msg(parse.message, cur, conn):
            return
        # chat_id = parse.message.chat_id
        # loss = parse.loss
        # text = 'LOST\n'+'\n'.join(['{}: {}шт'.format(k, v) for k, v in loss.items()])
        # self.message_manager.send_message(text=text, chat_id=chat_id, parse_mode='HTML', disable_web_page_preview=True)

    def handle_building(self, cur: sql.Cursor, conn: sql.Connection, parse: parser.ParseResult):
        if not parse.building:
            return
        uid = parse.message.from_user.id
        date = str(parse.message.forward_date)
        if (uid, date) not in self.building:
            if parse.timedelta < datetime.timedelta(seconds=300):
                self.building.add((uid, date))
                cur.execute('INSERT INTO building(id, time) VALUES(?, ?)', (uid, date))
                self.users[uid].stats[4].building += parse.building.trophy
                self.users[uid].stats[4].update_building(cur, uid, date)
                conn.commit()
                self.message_manager.send_message(chat_id=uid, text='Ок, апгрейд засчитан\nПродолжай в том же духе')
            else:
                self.message_manager.send_message(chat_id=uid, text='К сожалению, твой форвард уже протух\nЯ ем только'
                                                                    ' те, что свежее 5 минут')
        else:
            self.message_manager.send_message(chat_id=uid, text='Кажется, этот форфард я уже видел')

    def handle_command(self, cur, conn, parse: parser.ParseResult):
        message = parse.message
        text = message.text
        user = message.from_user
        chat_id = message.chat_id
        if not parse.command:
            return
        command, name, argument, modifier = parse.command.command, parse.command.name, parse.command.argument, \
                                            parse.command.modifier
        # TODO : rewrite all comands using argument rather than text
        if name == 'stat' and not argument and not message.reply_to_message:
            n = 5
            if modifier.isdigit():
                n = int(modifier)
                if n < 1 or n > 3 or self.users[user.id].stats[n - 1] is None:
                    s = [str(i + 1) + ", " for i in range(3) if self.users[user.id].stats[i] is not None]
                    s = "".join(s).strip(", ")
                    if not s:
                        self.message_manager.send_message(chat_id=chat_id, text="У тебя ещё нет сохранений")
                    else:
                        self.message_manager.send_message(chat_id=chat_id, text="Доступны сохранения " + s)
                    return
            elif modifier:
                self.message_manager.send_message(chat_id=user.id, text="Неверный формат команды")
                return
            self.stat(user.id, chat_id, n)
        elif name == 'stat':
            _, ids = self.demand_ids(message, user=user, all=True)
            n = 5
            if modifier.isdigit():
                n = int(modifier)
            for uid in ids:
                if self.no_permission(user, self.users[uid].squad) and uid != user.id:
                    self.message_manager.send_message(chat_id=chat_id,
                                                      text="Любопытство не порок\nНо меру то знать надо...\nСтатистика @"
                                                           + self.users[uid].username + " тебе не доступна")
                    return
                self.stat(uid, chat_id, n)
        elif name == 'change':
            n = 4
            player = self.users[user.id]
            if modifier.isdigit():
                n = int(modifier)
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
            self.change(user.id, chat_id, n)
        elif name == 'table':
            _, ids = self.demand_ids(message, user=user, all=True, offset=1)
            N = 5
            if modifier.isdigit():
                N = int(modifier)
            else:
                return
            if any(self.no_permission(user, self.users[uid].squad) for uid in ids):
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Статы кого-то из них тебе не доступны\nТочно знаю")
                return
            text = "юзерка; ник; хп; урон; бронь; сила; меткость; харизма; ловкость; рейды;стройка\n"
            lines = []
            for uid in ids:
                pl = self.users[uid]
                st0 = pl.stats[N - 1]
                st1 = pl.stats[4]
                lines.append("{};{};{};{};{};{};{};{};{};{};{}"
                             .format(pl.username, pl.nic, st1.hp - st0.hp, st1.attack - st0.attack,
                                     st1.deff - st0.deff, st1.power - st0.power, st1.accuracy - st0.accuracy,
                                     st1.oratory - st0.oratory, st1.agility - st0.agility, st1.raids - st0.raids,
                                     st1.building - st0.building))
            text += "\n".join(lines)
            self.message_manager.send_message(chat_id=chat_id, text=text)
        elif command == 'check_up':
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
                self.change(uid, chat_id, N)
        elif name == 'save':
            n = 5
            if modifier.isdigit():
                n = int(modifier)
            if not 1 <= n <= 3:
                self.message_manager.send_message(chat_id=user.id, text="Куда-то не туда сохраняешь...")
                return
            player = self.users[user.id]
            ps = player.get_stats(4)
            player.set_stats(cur, ps, n - 1)
            conn.commit()
            self.message_manager.send_message(chat_id=chat_id,
                                              text="Текущая статистика сохранена в ячейку №" + str(n))
        elif command == 'top':
            self.top(user.id, user.username, chat_id, text, StatType.ALL, time=message.date)
        elif command == 'rushtop':
            self.top(user.id, user.username, chat_id, text, StatType.ATTACK, time=message.date)
        elif command == 'hptop':
            self.top(user.id, user.username, chat_id, text, StatType.HP, time=message.date)
        elif command == 'acctop':
            self.top(user.id, user.username, chat_id, text, StatType.ACCURACY, time=message.date)
        elif command == 'agtop':
            self.top(user.id, user.username, chat_id, text, StatType.AGILITY, time=message.date)
        elif command == 'ortop':
            self.top(user.id, user.username, chat_id, text, StatType.ORATORY, time=message.date)
        elif command == 'raidtop':
            self.top(user.id, user.username, chat_id, text, StatType.RAIDS, time=message.date)
        elif command == 'uptop':
            self.top(user.id, user.username, chat_id, text, StatType.BUILD, time=message.date)
        # elif command == 'players':
        #    self.top(user.id, user.username, chat_id, text, StatType.ALL, invisible=True, title="Игроки",
        #             time=message.date)
        elif command == "new_squad" and (user.id in self.admins) and (
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
            self.add_squad(cur, self.usersbyname[master], short.lower(), message.chat.title, user.id, chat_id)
            conn.commit()
        elif command == "make_master":
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
            if self.add_master(cur, self.usersbyname[master], user.id, short):
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="Теперь @" + master + " командир <b>" + short + "</b>",
                                                  parse_mode='HTML')
            conn.commit()
        elif command == 'disgrace':
            _, ids = self.demand_ids(message, user=user, all=True)
            for uid in ids:
                if self.del_master(cur, uid, user.id):
                    self.message_manager.send_message(chat_id=chat_id, text="Больше он не командир\nИ вообще никто")
            conn.commit()
        elif command == "add":
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
        elif name == 'echo':
            type = modifier
            if type:
                type = type.strip()
            status = None  # TODO consider using dict instead
            if not type:
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
            sqs, msg = self.demand_squads(text, user, allow_empty_squads=True)
            if sqs is None:
                return
            if not sqs and user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Ты не одмен, тебе не можно")
                return
            if not msg:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="А писать-то и нечего")
                return
            self.echo(msg, self.users[user.id].chatid, sqs, status)
        elif command == "echo-s":
            sqs, msg = self.demand_squads(text, user)
            if sqs:
                for sq in sqs:
                    self.message_manager.send_message(chat_id=self.squadids[sq], text=msg,
                                                      reply_markup=telega.ReplyKeyboardRemove())
                self.message_manager.send_message(chat_id=self.users[user.id].chatid, text="Ваш зов был услышан")
        elif command == "pin":
            sqs, msg = self.demand_squads(text, user)
            if sqs:
                for sq in sqs:
                    self.message_manager.pin(chat_id=self.squadids[sq], text=msg, uid=chat_id)
        elif command == "rename":
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
        elif command == "title":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Нужно больше власти")
                return
            title, ids = self.demand_ids(message, user=user, all=False)
            if not ids or not title:
                return
            for uid in ids:
                pl = self.users[uid]
                pl.add_title(cur, title)
                conn.commit()
                text = '@{} присвоено звание «{}»'.format(pl.username, title)
                self.message_manager.send_message(chat_id=chat_id, text=text)
            return
        elif command == "title_del":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Нужно больше власти")
                return
            title, ids = self.demand_ids(message, user=user, all=False)
            if not ids or not title:
                return
            for uid in ids:
                pl = self.users[uid]
                pl.del_title(cur, title)
                conn.commit()
                text = '@{} больше не {}'.format(pl.username, title)
                self.message_manager.send_message(chat_id=chat_id, text=text)
            return
        elif command == "title_clear":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Нужно больше власти")
                return
            _, ids = self.demand_ids(message, user=user, all=True)
            if not ids:
                return
            for uid in ids:
                pl = self.users[uid]
                pl.clear_titles(cur)
                conn.commit()
                text = 'У @{} отобраны все звания. Оно того стоило?'.format(pl.username)
                self.message_manager.send_message(chat_id=chat_id, text=text)
            return
        elif command == "title_all":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Нужно намного больше власти")
                return
            titles = {}
            for pl in self.users.values():
                for tl in pl.titles:
                    if titles.get(tl):
                        titles[tl].append("@"+pl.username)
                    else:
                        titles[tl] = ["@"+pl.username]

            keys = list(titles.keys())
            keys.sort()
            text = "Присвоенные титулы:\n{}".format(
                '\n'.join(['<b>{}</b>:\n  {}'.format(key, '\n  '.join(titles[key])) for key in keys])
            )
            self.message_manager.send_split(text, chat_id, 50)
            return
        elif command == "ban":
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
        elif command == 'unban':
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
        elif command == "remove":
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
        elif command == "expel":
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
        elif command == "kick":
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
        elif command == "pinonkm":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                self.pinkm = PinOnlineKm(self.squadids, self.users, self.message_manager, self.db_path,
                                         timer=self.timer)
            sqs, msg = self.demand_squads(text, user)
            if sqs:
                for sq in sqs:
                    self.pinkm.pin(sq, self.users[user.id], msg)
        elif command == "closekm":
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
        elif command == "copykm":
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Что-то не вижу я у тебя админки?\nГде потерял?")
                return
            if self.pinkm is None:
                return
            self.pinkm.copy_to(chat_id)
        elif command.lower() == "viva_six":
            if chat_id not in self.viva_six.keys():
                self.viva_six[chat_id] = 0
            if self.viva_six[chat_id] % 2 == 0:
                self.message_manager.send_message(chat_id=chat_id, text="/VIVA_SIX")
            else:
                self.message_manager.bot.sendSticker(chat_id=chat_id, sticker="CAADAgADgAAD73zLFnbBnS7BK3KuAg")
            self.viva_six[chat_id] += 1
        elif command.lower() == "ave_khans":
            self.message_manager.bot.sendSticker(chat_id=chat_id, sticker="CAADAgADAQADmXkHGX_hmMWBv9rRAg")
        elif command == 'squads':
            self.list_squads(chat_id, (user.id in self.admins))
        elif command == 'whois':
            self.who_is(chat_id, text)
        elif command == 'whospy' or command == 'who_spy':
            self.who_spy(chat_id, user, message)
        elif command == 'raidson':
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
                    cur.execute(r'SELECT COUNT(*) FROM raids WHERE id = ? AND time > ?', (pl.id, start))
                    raids.append((int(cur.fetchone()[0]), pl.nic, pl.username))
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
            self.message_manager.send_split(msg, chat_id, 50)
        elif command == 'whoisonraid':
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
            msg = "Уже на точке({}):\n\t{}\nЕщё в пути({}):\n\t{}\nНе могут ходить так далеко({}):\n\t{}\nНе соизволили пойти({}):\n\t{}\nПропали без вести({}):\n\t{}".format(
                len(onplace), "\n\t".join(onplace), len(going), "\n\t".join(going), len(scared), "\n\t".join(scared),
                len(skipping), "\n\t".join(skipping), len(unknown), "\n\t".join(unknown)
            )
            if sq:
                msg = "В отряде <b>" + self.squadnames[sq] + "</b>\n" + msg
            self.message_manager.send_split(msg, chat_id, 100)
        elif command == 'autoping':
            if self.pinkm is None:
                self.message_manager.send_message(chat_id=chat_id, text="Пина нету")
                return
            squad_list, message_text = self.demand_squads(text, user, allow_empty_squads=False, default_message="Пин видели? А он вас нет...")
            if not squad_list:
                return
            for squad in squad_list:
                squad_messages = []
                list_to_ping = []
                for user in self.users.values():
                    if user.squad == squad and self.pinkm.player_status(user) == PinOnlineKm.PlayerStatus.UNKNOWN:
                        list_to_ping.append('@' + user.username)
                        if len(list_to_ping) == 3:
                            squad_messages.append(" ".join(list_to_ping))
                            list_to_ping.clear()
                if list_to_ping:
                    squad_messages.append(" ".join(list_to_ping))
                if squad_messages:
                    self.message_manager.send_message(chat_id=self.squadids[squad], text=message_text)
                    for message in squad_messages:
                        self.message_manager.send_message(chat_id=self.squadids[squad], text=message)
                else:
                    message = "Весь отряд {} уже отметился, круто!".format(squad)
                    self.message_manager.send_message(chat_id=chat_id, text=message)

        elif command == 'info':
            _, ids = self.demand_ids(message, user, all=True, allow_empty=True)
            if not ids:
                return
            for uid in ids:
                pl = self.users[uid]
                sq = "из отряда <b>{}</b>".format(
                    self.squadnames[pl.squad]) if pl.squad in self.squadnames.keys() else ""
                text = "Это <b>{0}</b> {1}".format(pl.nic, sq)
                if pl.titles:
                    text = '{}\n{}'.format(text, '\n'.join(['<code>' + tl + '</code>' for tl in pl.titles]))
                self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode='HTML',
                                                  disable_web_page_preview=True)
        elif command == 'who_is_at_command':
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=chat_id,
                                                  text="А ты смелый! Просить меня о таком...")
                return
            text = "<b>Админы</b>\n\t{}\n\n<b>Командиры</b>\n\t{}".format(
                "\n\t".join(["@" + self.users[uid].username for uid in self.admins]),
                "\n\t".join(["{} <b>{}</b>".format('@{}'.format(self.users[uid].username) if uid in self.users else '#{}'.format(uid), " ".join(self.masters[uid]))
                             for uid in self.masters.keys()]))
            self.message_manager.send_split(text, chat_id, 50)
        elif command == 'when_raid':
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
        elif command == 'add_trigger':
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=chat_id, text="Не не не. Ради тебя я на это не пойду")
                return
            res = self.add_trigger(argument, cur)
            if not res:
                self.message_manager.send_message(chat_id=chat_id, text="Не удалось добавить тригер")
                return
            self.message_manager.send_message(chat_id=chat_id, text="Добавлен тригер\n/{} : {}".format(res[0], res[1]),
                                              parse_mode="HTML")
            conn.commit()
        elif command == 'all_triggers':
            tgs = []
            for sq, dic in self.triggers.items():
                if not user.id in self.admins and sq != 'all' and sq != self.squads_by_id.get(chat_id):
                    continue
                for tg in dic.keys():
                    tgs.append('/'+ tg + " (%s)" % sq)
            text = "Доступные тригеры:\n%s" % ("\n".join(tgs))
            self.message_manager.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        elif command == 'del_trigger':
            if user.id not in self.admins:
                self.message_manager.send_message(chat_id=chat_id, text="Не не не. Ради тебя я на это не пойду")
                return
            res = self.del_trigger(argument, cur)
            if not res:
                self.message_manager.send_message(chat_id=chat_id, text="Не удалось удалить тригер")
                return
            conn.commit()
            self.message_manager.send_message(chat_id=chat_id, text="Удален тригер\n/{}".format(res),
                                              parse_mode="HTML")
        elif self.trigger(command, chat_id):
            pass
        else:
            if message.chat.type == "private":
                self.message_manager.send_message(chat_id=self.users[user.id].chatid,
                                                  text="Неизвестная команда... Сам придумал?")

    def start(self):
        self.updater.start_polling(clean=True)
        self.updater.idle()
    
    def stop(self):
        self.updater.stop()
        self.message_manager.stop()
        if self.notificator:
            self.notificator.stop()
        self.timer.stop()

    def handle_massage(self, bot, update: telega.Update):
        if update.channel_post:
            self.handle_post(update.channel_post)
            return
        if update.message and update.message.forward_from_chat and update.message.forward_from_chat.username.lower() == 'greatwar':
            self.handle_post_forward(update)
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
        if parse_result.profile is not None and message.chat.type == "private":
            profile = parse_result.profile
            if user.id not in self.users.keys():
                if profile.fraction != "⚙️Убежище 6":
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
                player.nic = profile.nic
            elif player.nic != profile.nic:
                self.message_manager.send_message(chat_id=player.chatid,
                                                  text="🤔 Раньше ты играл под другим ником.\nМожешь отправить <b>свежий</b> профиль?\n<i>Успей переслать его из игрового бота за 15 секунд</i>\n"
                                                       "Если ты сменил игровой ник и у тебя лапки обратись к @ant_ant или своему командиру\n"
                                                       "<code>А иначе не кидай мне чужой профиль!</code>",
                                                  parse_mode='HTML')
                player.update_text(cur)
                conn.commit()
                return
            player.update_text(cur)

            oldps = player.get_stats(4)
            ps = profile.stats
            ps.raids = 0
            if oldps is not None:
                player.set_stats(cur, oldps, 3)
                ps.raids = oldps.raids
                ps.building = oldps.building
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

        processed_forward = False
        if parse_result.pve is not None:
            self.handle_pve(parse_result, cur, conn)
            processed_forward = True
        elif parse_result.pvp is not None:
            self.handle_pvp(parse_result, cur, conn)
            processed_forward = True
        elif parse_result.meeting is not None:
            self.handle_meeting(parse_result, cur, conn)
            processed_forward = True
        elif parse_result.getto is not None:
            self.handle_getto(parse_result, cur, conn)
            processed_forward = True
        elif parse_result.loot:
            self.handle_loot(parse_result, cur, conn)
            processed_forward = True
        elif parse_result.loss:
            self.handle_loss(parse_result, cur, conn)
            processed_forward = True


        if processed_forward:
            return
        if parse_result.command:
            self.handle_command(cur, conn, parse_result)
            if message.chat.type == "private":
                self.message_manager.send_message(reply_markup=self.keyboards[self.users[user.id].keyboard])
        elif parse_result.building:
            self.handle_building(cur, conn, parse_result)
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
                        self.info(player)
                        return
                    elif text == "👨‍💻 О жизни":
                        self.guide(player)
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
                        s = self.top(user.id, user.username, chat_id, "", StatType.ALL, time=message.date,
                                     textmode=True)
                    elif text == "⚔️ Дамагеры":
                        ctext = "rushtop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.ATTACK, time=message.date,
                                     textmode=True)
                    elif text == "❤️ Танки":
                        ctext = "hptop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.HP, time=message.date,
                                     textmode=True)
                    elif text == "🤸🏽‍♂️ Ловкачи":
                        ctext = "agtop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.AGILITY, time=message.date,
                                     textmode=True)
                    elif text == "🔫 Снайперы":
                        ctext = "acctop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.ACCURACY, time=message.date,
                                     textmode=True)
                    elif text == "🗣 Дипломаты":
                        ctext = "ortop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.ORATORY, time=message.date,
                                     textmode=True)
                    elif text == "🔪 Рейдеры":
                        ctext = "raidtop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.RAIDS, time=message.date,
                                     textmode=True)
                    elif text == "🔨 Исследователи":
                        ctext = "uptop"
                        s = self.top(user.id, user.username, chat_id, "", StatType.BUILD, time=message.date,
                                     textmode=True)
                    # elif text == "📜 Полный список":
                    #    ctext = "players"
                    #    s = self.top(user.id, user.username, chat_id, "", StatType.ALL, invisible=True,
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
                        self.my_stat(player, 5)
                        return
                    elif text == '🔝 Прирост':
                        self.my_change(player, 4)
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

    def info(self, player: Player):
        text = "Перед вами стат бот 6 убежища <i>и он крут😎</i>\nОзнакомиться с его командами вы можете по ссылке" \
               " http://telegra.ph/StatBot-Redizajn-09-30\nНо для вашего же удобства рекомендую пользоваться графическим интерфейсом\n" \
               "Бот создан во имя блага и процветания 6 убежища игроком @ant_ant\n" \
               "Так что если найдете в нем серьезные баги - пишите мне)\nЕсли есть желание помочь - можете подкинуть" \
               " денег (https://qiwi.me/67f1c4c8-705c-4bb3-a8d3-a35717f63858) на поддержку бота или связаться со мной и записаться в группу альфа-тестеров\n" \
               "\n<i>Играйте, общайтесь, радуйтесь жизни! Вместе мы сильнейшая фракция в игре!</i>\n\n<i>P.S.: Бот продолжает развиваться. Дальше будет лучше</i>"
        self.message_manager.send_message(chat_id=player.chatid, text=text, parse_mode='HTML',
                                          disable_web_page_preview=True,
                                          reply_markup=self.keyboards[player.keyboard])

    def guide(self, player: Player, chat_id=None):
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

    def my_stat(self, player: Player, n, id=None):
        s = self.stat(player.id, player.chatid, n, textmode=True)
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

    def my_change(self, player: Player, n, id=None):
        s = self.change(player.id, player.chatid, n, textmode=True)
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
            if self.squads_by_id.get(chat_id) == 'v6' and user.id not in self.users.keys():
                self.message_manager.send_message(chat_id=-1001289414206, text="@{} замечен на просторах общего чата"
                                                  .format(user.username))

    def handle_callback(self, bot: telega.Bot, update: telega.Update):
        query = update.callback_query
        message = query.message
        chat_id = message.chat_id
        user = query.from_user
        if user.id not in self.users.keys():
            bot.answer_callback_query(callback_query_id=query.id, text="Мы еще не знакомы, го в лс")
            return
        self.update_apm(user.id)
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
            s = self.top(user.id, user.username, chat_id, data, StatType.ALL, time=message.date, textmode=True)
        elif text == "rushtop":
            s = self.top(user.id, user.username, chat_id, data, StatType.ATTACK, time=message.date, textmode=True)
        elif text == "hptop":
            s = self.top(user.id, user.username, chat_id, data, StatType.HP, time=message.date, textmode=True)
        elif text == "agtop":
            s = self.top(user.id, user.username, chat_id, data, StatType.AGILITY, time=message.date, textmode=True)
        elif text == "acctop":
            s = self.top(user.id, user.username, chat_id, data, StatType.ACCURACY, time=message.date,
                         textmode=True)
        elif text == "ortop":
            s = self.top(user.id, user.username, chat_id, data, StatType.ORATORY, time=message.date, textmode=True)
        elif text == "raidtop":
            s = self.top(user.id, user.username, chat_id, data, StatType.RAIDS, time=message.date, textmode=True)
        elif text == "uptop":
            s = self.top(user.id, user.username, chat_id, data, StatType.BUILD, time=message.date, textmode=True)
        elif text == "players":
            s = self.top(user.id, user.username, chat_id, data, StatType.ALL, invisible=True, title="Игроки",
                         time=message.date, textmode=True)
        elif text == "stat":
            self.my_stat(self.users[user.id], int(name) + 1, message.message_id)
        elif text == "change":
            self.my_change(self.users[user.id], int(name) + 1, message.message_id)
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
    if os.getenv('DEBUG'):
        set_stderr_debug_logger()

    stat_bot = Bot()
    stat_bot.start()

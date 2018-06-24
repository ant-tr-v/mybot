import telegram as telega
import re
import datetime

from ww6StatBotUtils import MessageManager
from ww6StatBotPlayer import PlayerStat


class Command:
    def __init__(self, match=None):
        self.command = None
        self.name = None
        self.argument = None
        self.modifier = None
        if match:
            try:
                self.command = match.group('command') or ""
                self.name = match.group('name') or ""
                self.argument = match.group('argument') or ""
                self.modifier = match.group('modifier') or ""
            except:
                pass


class Build:
    def __init__(self, match=None):
        self.where = None
        self.trophy = None
        self.what = None
        self.percent = None
        if match:
            try:
                self.where = match.group('where') or ""
                self.trophy = int(match.group('trophy') or "0")
                self.what = match.group('what') or ""
                self.percent = int(match.group('percent') or "0")
            except:
                pass

    def __repr__(self):
        return "where: {}\nwhat: {}\ntrophy: {}\npercent: {}\n".format(self.where or "---", self.what or "---",
                                                                       self.trophy or "---", self.percent or "---")


class Profile:
    def __init__(self, match=None):
        self.nic = None
        self.fraction = None
        self.stats = None
        self.hp_now = None
        self.stamina_now = None
        self.hunger = None
        self.distance = None
        self.location = None
        if match:
            self.nic, self.fraction, self.location = match.group('nic', 'fraction', 'location')
            self.nic = self.nic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            hp, hp_now, hunger, attack, armor, power, accuracy, oratory, agility, stamina, stamina_now, distance = \
                [int(x) for x in match.group('hp', 'hp_now', 'hunger', 'attack', 'armor', 'power', 'accuracy', 'oratory',
                                             'agility', 'stamina', 'stamina_now', 'distance')]
            self.hp_now, self.stamina_now, self.distance = hp_now, stamina_now, distance
            self.stats = PlayerStat()
            self.stats.hp, self.stats.stamina, self.stats.agility, self.stats.oratory, self.stats.accuracy, \
            self.stats.power, self.stats.attack, self.stats.deff = hp, stamina, agility, oratory, accuracy, power, \
                                                                   attack, armor

class ParseResult:
    def __init__(self):
        self.message = None
        self.username = None
        self.raid_text = None
        self.raid_time = None
        self.timedelta = None
        self.command = None
        self.building = None
        self.profile = None


class Parser:
    def __init__(self, message_manager: MessageManager, bot_name):
        self.message_manager = message_manager
        self.WASTELAND_CHAT = 430930191
        self.raid_format = re.compile(
            r'(Рейд[\s]+(?P<msg>в[\s]+((?P<hour>[\d]+)|([-]+)):[\d]+[\s]*((?P<day>[\d]+)\.(?P<month>[\d]+))?.*\n.*))')
        self.re_command = re.compile(
            r'/(?P<command>(?P<name>[^\s_@]+)(_(?P<modifier>[^\s@]+))?)({})?\s*(?P<argument>.*)'.format(
                bot_name),
            re.DOTALL)
        self.re_trophy = re.compile(r'Твои 🎗Трофеи:[\s]+[\d]+[\s]+шт.[\s]+(?P<where>[^\n]+)[\s]+'
                                    r'Ты инвестировал в это исследование[\s]+(?P<trophy>[\d]+)[\s]+трофеев.[\s]+'
                                    r'Исследование:[\s]+(?P<what>[^\n]+)[\s]+Прогресс:[\s]+(?P<percent>[\d]+)')
        self.re_profile = re.compile(r'\n(?P<nic>[^\n]*)\n👥Фракция:[\s]*(?P<fraction>[^\n]*)[\s]+'
                                     r'❤️Здоровье:[\s]+(?P<hp_now>[\d]+)/(?P<hp>[\d]+)[\s]+🍗Голод:[\s]+(?P<hunger>[\d]+)%'
                                     r'[\s]+⚔️Урон:[\s]+(?P<attack>[\d]+)[\s]+🛡Броня:[\s]+(?P<armor>[\d]+)[\s]+'
                                     r'💪Сила:[\s]+(?P<power>[\d]+)[\s]+🔫Меткость:[\s]+(?P<accuracy>[\d]+)[\s]+'
                                     r'🗣Харизма:[\s]+(?P<oratory>[\d]+)[\s]+🤸🏽‍♂️Ловкость:[\s]+(?P<agility>[\d]+)[\s]+'
                                     r'🔋Выносливость:[\s]+(?P<stamina_now>[\d]+)/(?P<stamina>[\d]+)[\s]+'
                                     r'🔥Локация:[\s]+(?P<location>[^\n]*)\n👣Расстояние:[\s]+(?P<distance>[\d]+)')
        self.re_profile_short = re.compile(
            r'👤(?P<nic>[^\n]*)\n├(?P<fraction>[^\n]*)\n├❤️(?P<hp_now>[\d]+)/(?P<hp>[\d]+)'
            r'[^\d]+(?P<hunger>[\d]+)[^\d]+(?P<attack>[\d]+)[^\d]+[^\d]*(?P<armor>[\d]+)'
            r'[^\d]+(?P<power>[\d]+)[^\d]+[^\d]*(?P<accuracy>[\d]+)'
            r'[^\d]+(?P<oratory>[\d]+)[^\d]+(?P<agility>[\d]+)'
            r'[^\d]+(?P<stamina_now>[\d]+)/(?P<stamina>[\d]+)[^\d]+👣(?P<distance>[\d]+)\n'
            r'├🔥(?P<location>[^\n]+)')

    def _parse_forward(self, message: telega.Message, pr: ParseResult):
        match = self.re_profile.search(message.text) or self.re_profile_short.search(message.text)
        if match:
            pr.profile = Profile(match)
            pr.profile.stats.time = message.forward_date


    def _parse_raid(self, message: telega.Message, pr: ParseResult):
        text = message.text
        m = self.raid_format.search(text)
        if m:
            date = message.forward_date
            try:
                hour = m.group('hour')
                day = m.group('day')
                month = m.group('month')
                ddate = None
                if hour is None:
                    h = (((int(date.hour) % 24) - 1) // 6) * 6 + 1
                    d = 0
                    if h < 0:
                        h = 19
                        d = -1
                    ddate = datetime.datetime(year=date.year, month=date.month, day=date.day,
                                              hour=h) + datetime.timedelta(days=d)
                elif day is None:
                    ddate = datetime.datetime(year=date.year, month=date.month, day=date.day,
                                              hour=int(hour) % 24)
                    if message.forward_date - ddate < -datetime.timedelta(seconds=1):
                        ddate = ddate - datetime.timedelta(days=1)
                else:
                    ddate = datetime.datetime(year=date.year, month=int(month), day=int(day),
                                              hour=int(hour) % 24)
                    if message.forward_date - ddate < -datetime.timedelta(seconds=1):
                        ddate = datetime.datetime(ddate.year - 1, ddate.month, ddate.day, ddate.hour)

                date = str(ddate).split('.')[0]
                pr.raid_text = m.group('msg')
                pr.raid_time = date
            except:
                return

    def _parse_command(self, msg: telega.Message, pres: ParseResult):
        com = Command(self.re_command.match(msg.text))
        if com.command:
            pres.command = com

    def _parse_build(self, msg: telega.Message, pres: ParseResult):
        bld = Build(self.re_trophy.match(msg.text))
        if bld.what:
            pres.building = bld

    def run(self, msg: telega.Message):
        res = ParseResult()
        res.message = msg
        res.username = msg.from_user.username
        self._parse_command(msg, res)
        res.timedelta = datetime.datetime.now() - msg.forward_date if (msg.forward_from is not None) else 0
        if (msg.forward_from is not None) and (msg.forward_from.id == self.WASTELAND_CHAT):
            self._parse_forward(msg, res)
            self._parse_raid(msg, res)
            self._parse_build(msg, res)

            # if res.building:
            #     self.message_manager.send_message(chat_id=msg.from_user.id, text=str(res.building))
            # self.message_manager.send_message(chat_id=msg.from_user.id, text=str(res))
        return res

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


class ParseResult:
    def __init__(self):
        self.message = None
        self.stats = None
        self.fraction = None
        self.nic = None
        self.username = None
        self.raid_text = None
        self.raid_time = None
        self.timedelta = None
        self.command = None
        self.building = None

    def __str__(self):
        return "stats: {}\nfrac: {}\nnic: {}, username: {}\nraid_text: {}\n"\
            .format('+' if self.stats else "-", self.fraction or "-", self.nic or '-',
                    self.username or '-', self.raid_text or '-')


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

    @staticmethod
    def _parse_forward(message: telega.Message, pr: ParseResult):
        # TODO rewrite using re
        text = message.text.strip(" \n\t")
        tlines = text.split("\n")
        ps = None

        nic = ""
        try:
            ps = PlayerStat()
            n = -1
            for i in range(1, len(tlines)):
                if tlines[i] and tlines[i][0] == '├' and tlines[i - 1][0] == '├':
                    n = i - 2
                    break
            if n >= 0:
                pr.fraction = tlines[n + 1][1:]
                nic = tlines[n][1:]
                ps.hp, hanger, ps.attack, ps.deff = [int("".join([c for c in x if c.isdigit()])) for x in
                                                     tlines[n + 2][tlines[n + 2].find("/"):].split('|')]
                ps.power, ps.accuracy = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n + 3].split('|')]
                ps.oratory, ps.agility = [int("".join([c for c in x if c.isdigit()])) for x in tlines[n + 4].split('|')]
                m = re.search(r"[\d]+/(?P<stamina>[\d]+)", tlines[n + 5])
                ps.stamina = int(m.group('stamina')) if m else 5
            else:
                nl = 2  # МАГИЧЕСКАЯ КОНСТАНТА номер строки с ником игрока [первый возможный]
                while nl < len(tlines):
                    m = re.search(r'Фракция:(?P<val>.+)', tlines[nl + 1])
                    if m:
                        pr.fraction = m.group('val').strip()
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
                        ps.accuracy = int(m.group('val'))
                    m = re.search(r'Харизма:[\s](?P<val>[\d]+)', tlines[i])
                    if m:
                        ps.oratory = int(m.group('val'))
                    m = re.search(r'Ловкость:[\s](?P<val>[\d]+)', tlines[i])
                    if m:
                        ps.agility = int(m.group('val'))
                    m = re.search(r'Выносливость:[\s][\d]+/(?P<val>[\d]+)', tlines[i])
                    if m:
                        ps.stamina = int(m.group('val'))
            ps.time = message.forward_date
            nic = nic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        except:
            pass
        else:
            pr.nic = nic
            pr.stats = ps

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

    def _parse_command(self, msg:telega.Message, pres:ParseResult):
        com = Command(self.re_command.match(msg.text))
        if com.command:
            pres.command = com

    def _parse_build(self, msg:telega.Message, pres:ParseResult):
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

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
        self.crew = None
        self.stats = None
        self.hp_now = None
        self.stamina_now = None
        self.hunger = None
        self.distance = None
        self.location = None
        if match:
            self.nic, self.fraction, self.crew, self.location = match.group('nic', 'fraction', 'crew', 'location')
            self.nic = self.nic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            hp, hp_now, hunger, attack, armor, power, accuracy, oratory, agility, stamina, stamina_now, distance = \
                [int(x) for x in
                 match.group('hp', 'hp_now', 'hunger', 'attack', 'armor', 'power', 'accuracy', 'oratory',
                             'agility', 'stamina', 'stamina_now', 'distance')]
            self.hp_now, self.stamina_now, self.distance = hp_now, stamina_now, distance
            self.stats = PlayerStat()
            self.stats.hp, self.stats.stamina, self.stats.agility, self.stats.oratory, self.stats.accuracy, \
            self.stats.power, self.stats.attack, self.stats.deff = hp, stamina, agility, oratory, accuracy, power, \
                                                                   attack, armor


class InfoLine:
    def __init__(self, match=None):
        self.hp_now = None
        self.stamina_now = None
        self.hunger = None
        self.distance = None
        if match:
            self.hp_now, self.stamina_now, self.hunger, self.distance = \
                [int(x) for x in match.group('hp_now', 'stamina_now', 'hunger', 'distance')]


class PVP:
    def __init__(self):
        self.nics = []
        self.dd = {}
        self.win = None


class PVE:
    def __init__(self):
        self.damage_dealt = []
        self.damage_taken = []
        self.win = None
        self.mob_nic = None
        self.dunge = None


class Meeting:
    def __init__(self):
        self.fraction = None
        self.nic = None


class ParseResult:
    def __init__(self):
        self.message = None
        self.username = None
        self.raid_text = None
        self.raid_time = None
        self.raid_loc = None
        self.timedelta = None
        self.command = None
        self.building = None
        self.profile = None
        self.info_line = None
        self.loot = None
        self.loss = None
        self.pvp = None
        self.pve = None
        self.meeting = None
        self.getto = None


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
                                     r'(🤟Банда:\s+(?P<crew>[^\n]*)\s+)?'
                                     r'❤️Здоровье:[\s]+(?P<hp_now>[\d]+)\/(?P<hp>[\d]+)[\s]+'
                                     r'🍗Голод:[\s]+(?P<hunger>[\d]+)%[\s]+'
                                     r'⚔️Урон:[\s]+(?P<attack>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'🛡Броня:[\s]+(?P<armor>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'💪Сила:[\s]+(?P<power>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'🔫Меткость:[\s]+(?P<accuracy>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'🗣Харизма:[\s]+(?P<oratory>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'🤸🏽‍♂️Ловкость:[\s]+(?P<agility>[\d]+)([\s]*\([^)]*\))?[\s]*'
                                     r'🔋Выносливость:[\s]+(?P<stamina_now>[\d]+)\/(?P<stamina>[\d]+)[\s]+'
                                     r'🔥Локация:[\s]+(?P<location>[^\n]*)\n👣Расстояние:[\s]+(?P<distance>[\d]+)')
        self.re_profile_short = re.compile(
            r'👤(?P<nic>[^\n]*)\n├🤟 (?P<crew>[^\n]*)\n├(?P<fraction>[^\n]*)\n'
            r'├❤️(?P<hp_now>[\d]+)\/(?P<hp>[\d]+)[^\d]+(?P<hunger>[\d]+)[^\d]+'
            r'(?P<attack>[\d]+)[^\d]+[^\d]*(?P<armor>[\d]+)[^\d]+'
            r'(?P<power>[\d]+)[^\d]+[^\d]*(?P<accuracy>[\d]+)[^\d]+'
            r'(?P<oratory>[\d]+)[^\d]+(?P<agility>[\d]+)[^\d]+'
            r'(?P<stamina_now>[\d]+)\/(?P<stamina>[\d]+)[^\d]+'
            r'👣(?P<distance>[\d]+)\n├🔥(?P<location>[^\n]+)')

        self.re_info_line = re.compile(r'❤️(?P<hp_now>-?\d+)/(?P<hp>\d+)\s*🍗(?P<hunger>\d+)%\s*'
                                          r'🔋(?P<stamina_now>\d+)/(?P<stamina>\d+)\s*👣(?P<distance>\d+)км')

        self.re_pve = re.compile(r'Сражение с\s*(?P<mob>.*)')
        self.re_pve_win = re.compile('Ты одержал победу!')
        self.re_pve_dt = re.compile('💔(-?\d+)')
        self.re_pve_dd = re.compile('💥(-?\d+)')

        self.re_loot_caps = re.compile(r'\n\s*(Ты заработал:|Получено крышек:|Найдено крышек:)\s*🕳(\d+)')
        self.re_loot_mats = re.compile(r'\n\s*(Получено материалов:|Получено:|Собрано материалов:)\s*📦(\d+)')
        self.re_loot_other = re.compile(r'\n\s*Получено:\s*([^📦].*)')
        self.re_loot_mult = re.compile(r'\s*х?(\d+)\s*$')

        self.re_loss_caps = re.compile(r'(\n\s*Потеряно крышек:|Ты потерял:)\s*🕳(\d+)')
        self.re_loss_mats = re.compile(r'(\n\s*Потеряно материалов:|Проебано:)\s*📦(\d+)')
        self.re_loss_dead = re.compile(r'\n\s*Потеряно:\s*🕳(\d+)\s*и\s*📦(\d+)')

        self.re_enemy = re.compile(r'нашивка: (?P<fraction>⚙️Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы)')
        self.re_friend = re.compile(r'знакомый:\n(?P<nic>.*) из "(?P<fraction>⚙️Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы)!"')
        self.re_maniak = re.compile(r'\nЭто (?P<nic>.*) из (?P<fraction>⚙️Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы)')
        self.re_player_in_brackets = re.compile(r'(?P<nic>.*)\((?P<fraction>⚙️Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы)\)')
        self.re_getto = re.compile(r'Игроки в белом гетто')

        self.re_pvp = re.compile(r'(?P<nic1>.*)из (?P<frac1>(Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы))\s*VS.\s*'
                                 r'(?P<nic2>.*)из (?P<frac2>(⚙️Убежище 4|⚙️Убежище 6|💣Мегатонна|🔪Головорезы))\s*FIGHT!')
        self.re_pvp_line = re.compile(r'❤\S+(.*)\(💥(\d+)\)')

        self.re_raid_locs = [(re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*📦'), 5),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🕳'), 9),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔹'), 20),
                     (re.compile(r"🕳\s*\+\d+\s*📦\s*\+\d+\s*((❤️|❤)\s*\+\s*\d+,\s*)?Эффедрин"), 24),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*💡'), 28),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*💾'), 32),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔩'), 38),
                     (re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*🔗'), 46)
                     ]
        self.re_raid_msg_default = re.compile(r'🕳\s*\+\d+\s*📦\s*\+\d+\s*(.*)')

        self.food = {'Луковица', 'Помидор', 'Конфета', 'Булочка', 'Морковь', 'Человечина', 'Эдыгейский сыр',
                     'Мясо белки', 'Собачатина', r'Абрик\*с', 'Сухари', 'Чипсы', 'Голубь', 'Сырое мясо', 'Мясо утки',
                     'Хомячок', 'Красная слизь', 'Луковица', 'Сухофрукты', 'Молоко брамина', 'Вяленое мясо',
                     'Тесто в мясе', 'Сахарные бомбы', 'Консервы', 'Радсмурф', 'Мутафрукт', 'Что-то тухлое',
                     'Гнилой апельсин', 'Гнилое мясо', 'Не красная слизь'}
        self.drugs = {'Холодное пиво', 'Виски', 'Бурбон', 'Абсент', 'Глюконавт', 'Психонавт', 'Ментаты', 'Психо',
                      'Винт', 'Ультравинт', 'Скума'}



    def _parse_info_line(self, message: telega.Message, pr: ParseResult):
        match = self.re_info_line.search(message.text or '')
        if match:
            pr.info_line = InfoLine(match)

    def _parse_getto(self, message: telega.Message, pr: ParseResult):
        text = message.text or ''
        if not self.re_getto.match(text):
            return
        pr.getto = []
        for m in self.re_player_in_brackets.finditer(text):
            met = Meeting()
            met.nic = m.group('nic').strip()
            met.fraction = m.group('fraction')
            pr.getto.append(met)

    def _parse_meeting(self, message: telega.Message, pr: ParseResult):
        text = message.text or ''
        m = self.re_friend.search(text) or self.re_maniak.search(text)
        if not m and message.caption:
            m =self.re_player_in_brackets.search(message.caption)
        if m:
            pr.meeting = Meeting()
            pr.meeting.nic = m.group('nic').strip()
            pr.meeting.fraction = m.group('fraction')
        else:
            m = self.re_enemy.search(text)
            if m:
                pr.meeting = Meeting()
                pr.meeting.fraction = m.group('fraction')

    def _parse_pve(self, message: telega.Message, pr: ParseResult):
        """
        should be called only after _parse_info_line
        """
        text = message.text or ''
        if pr.info_line is None:
            return
        match = self.re_pve.search(text)
        if match:

            pr.pve = PVE()
            pr.pve.mob_nic = match.group('mob')
            pr.pve.mob_nic = pr.pve.mob_nic.strip()
            pr.pve.win = self.re_pve_win.search(text) is not None
            pr.pve.damage_dealt = [int(m.group(1)) for m in self.re_pve_dd.finditer(text)]
            pr.pve.damage_taken = [-int(m.group(1)) for m in self.re_pve_dt.finditer(text)]

    def _parse_loot(self, message: telega.Message, pr: ParseResult):
        pr.loot = {}
        pr.loss = {}
        text = message.text or ''
        caps = sum([int(m.group(2)) for m in self.re_loot_caps.finditer(text)])
        mats = sum([int(m.group(2)) for m in self.re_loot_mats.finditer(text)])
        caps_loss = sum([int(m.group(2)) for m in self.re_loss_caps.finditer(text)])
        mats_loss = sum([int(m.group(2)) for m in self.re_loss_mats.finditer(text)])
        dead_match = self.re_loss_dead.search(text)
        if dead_match:
            caps_loss += int(dead_match.group(1))
            mats_loss += int(dead_match.group(2))

        if caps:
            pr.loot['🕳'] = caps
        if mats:
            pr.loot['📦'] = mats
        if caps_loss:
            pr.loss['🕳'] = caps_loss
        if mats_loss:
            pr.loss['📦'] = mats_loss

        for m in self.re_loot_other.finditer(text):
            loot = m.group(1)
            m_x = self.re_loot_mult.search(loot)
            k = 1
            if m_x:
                loot = loot[:m_x.start()]
                k = int(m_x.group(1))
            loot = loot.strip()
            if loot in pr.loot.keys():
                pr.loot[loot] += k
            else:
                pr.loot[loot] = k

    def _parse_pvp(self, message: telega.Message, pr: ParseResult):
        text = message.text or ''
        match = self.re_pvp.search(text)
        if match:
            pr.pvp = PVP()
            pr.pvp.nics = [s.strip() for s in  match.group('nic1', 'nic2')]
            pr.pvp.dd = {x: [] for x in pr.pvp.nics}
            last = None
            for line in self.re_pvp_line.finditer(text):
                text = line.group(1).strip()
                dmg = int(line.group(2))
                pl = 0
                if text.find(pr.pvp.nics[1]) == 0:
                    pl = 1
                last = pr.pvp.nics[pl]
                pr.pvp.dd[last].append(dmg)
            pr.pvp.win = last


    def _parse_forward(self, message: telega.Message, pr: ParseResult):
        text = message.text or ''
        match = self.re_profile.search(text) or self.re_profile_short.search(text)
        if match:
            pr.profile = Profile(match)
            pr.profile.stats.time = message.forward_date

    def _parse_raid_msg(self, msg: str,  pr: ParseResult):
        rkm = -1
        for re_l, km in self.re_raid_locs:
            if re_l.search(msg):
                rkm = km
                break
        if rkm < 0:  # Special cases 12, 16
            m = self.re_raid_msg_default.search(msg)
            if m:
                rest = m.group(1)
                if any([re.match(val, rest) for val in self.food]):
                    rkm = 16
                elif any([re.match(val, rest) for val in self.drugs]):
                    rkm = 12
                pr.raid_loc = rkm if rkm > 0 else -1
        else:
            pr.raid_loc = rkm

    def _parse_raid(self, message: telega.Message, pr: ParseResult):
        text = message.text or ''
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
                msg  = pr.raid_text = m.group('msg')
                self._parse_raid_msg(msg, pr)
                pr.raid_time = date
            except:
                return

    def _parse_command(self, msg: telega.Message, pres: ParseResult):
        com = Command(self.re_command.match(msg.text or ''))
        if com.command:
            pres.command = com

    def _parse_build(self, msg: telega.Message, pres: ParseResult):
        bld = Build(self.re_trophy.match(msg.text or ''))
        if bld.what:
            pres.building = bld

    def run(self, msg: telega.Message):
        res = ParseResult()
        res.message = msg
        res.username = msg.from_user.username
        self._parse_command(msg, res)
        res.timedelta = datetime.datetime.now() - msg.forward_date if (msg.forward_from is not None) else 0
        if (msg.forward_from is not None) and (msg.forward_from.id == self.WASTELAND_CHAT):
            self._parse_info_line(msg, res)
            self._parse_forward(msg, res)
            self._parse_raid(msg, res)
            self._parse_build(msg, res)
            self._parse_pve(msg, res)
            self._parse_loot(msg, res)
            self._parse_pvp(msg, res)
            self._parse_meeting(msg, res)
            self._parse_getto(msg, res)

            # if res.building:
            #     self.message_manager.send_message(chat_id=msg.from_user.id, text=str(res.building))
            # self.message_manager.send_message(chat_id=msg.from_user.id, text=str(res))
        return res

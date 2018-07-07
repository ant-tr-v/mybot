import datetime
from enum import Enum
from telegram import User as telegram_User


class PlayerStat:
    def __init__(self):
        self.time = str(datetime.datetime.now())
        self.hp = 0
        self.attack = 0
        self.armor = 0
        self.power = 0
        self.accuracy = 0
        self.oratory = 0
        self.agility = 0
        self.stamina = 5

    def sum(self):
        return self.hp + self.attack + self.agility + self.accuracy + self.oratory

    def copy_stats(self, ps):
        self.time, self.hp, self.attack, self.armor, self.power, self.oratory, self.agility, self.accuracy, \
        self.stamina = ps.time, ps.hp, ps.attack, ps.armor, ps.power, ps.oratory, ps.agility, ps.accuracy, ps.stamina


class PlayerSettings:

    notification_time = ("23:00", "0:00", "1:05", "7:00", "8:00", "9:05", "15:00", "16:00", "17:05")

    def __init__(self):
        self.sex = "male"
        self.notifications = {t: False for t in self.notification_time}


class User:
    def __init__(self, usr: telegram_User = None):
        self.username = ""
        self.uid = 0
        if usr:
            self.uid = usr.id
            self.username = usr.username


class Player(User):
    class KeyboardType(Enum):
        NONE = -1
        DEFAULT = 0
        TOP = 1
        STATS = 2
        SETTINGS = 3

    def __init__(self, usr: telegram_User = None, nic=None):
        super().__init__(usr)
        self.nic = nic
        self.keyboard = self.KeyboardType.DEFAULT
        self.stats = PlayerStat()
        self.indexes = [None, None, None]
        self.squad = ''
        self.raids = 0
        self.building = 0
        self.karma = 0

    def __str__(self):
        return '<a href = "t.me/{}">{}</a>{}\n<b>\nДата:</b>{}{}{}{}{}{}{}{}{}{}{}'\
            .format(self.username, self.nic,
                    '\nОтряд:<b>{}</b>'.format(self.squad) if self.squad else '',self.stats.time,
                    '<b>\nЗдоровье:    </b>{}'.format(self.stats.hp) if self.stats.hp else '',
                    '<b>\nУрон:         </b>{}'.format(self.stats.attack) if self.stats.attack else '',
                    '<b>\nБроня:       </b>{}'.format(self.stats.armor) if self.stats.armor else '',
                    '<b>\nСила:         </b>{}'.format(self.stats.power) if self.stats.power else '',
                    '<b>\nМеткость:   </b>{}'.format(self.stats.accuracy) if self.stats.accuracy else '',
                    '<b>\nХаризма:    </b>{}'.format(self.stats.oratory) if self.stats.oratory else '',
                    '<b>\nЛовкость:  </b>{}'.format(self.stats.agility) if self.stats.agility else '',
                    '<b>\n\nУспешные рейды: </b>{}'.format(self.raids) if self.raids else '',
                    '<b>\nИсследования: </b>{}'.format(self.building) if self.building else '',
                    '<b>\nКарма: </b>{}'.format(self.karma) if self.karma else '')

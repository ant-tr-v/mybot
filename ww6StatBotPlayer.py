import datetime
from enum import Enum
from pytils.dt import distance_of_time_in_words
from telegram import User as telegram_User


class PlayerStat:
    def __init__(self):
        self.time = datetime.datetime.now()
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
        self.settings = PlayerSettings()
        self.indexes = [None, None, None]
        self.squad = ''
        self.raids = 0
        self.building = 0
        self.karma = 0

    def __int__(self):
        return self.uid

    def __hash__(self):
        return self.uid

    def __lt__(self, other):
        return self.uid < int(other)

    def __eq__(self, other):
        return self.uid == int(other)

    def __str__(self):
        time = self.stats.time
        now = datetime.datetime.now()
        return '<a href = "t.me/{}">{}</a>{}\n<b>\n📅Обновлено:</b>  {}{}{}{}{}{}{}{}{}{}{}{}' \
            .format(self.username, self.nic,
                    '\n📯Отряд:<b>{}</b>'.format(self.squad.title) if self.squad else '',
                    distance_of_time_in_words(time, accuracy=2, to_time=now),
                    '<b>\n❤️Здоровье:    </b>{}'.format(self.stats.hp) if self.stats.hp else '',
                    '<b>\n⚔️Урон:             </b>{}'.format(self.stats.attack) if self.stats.attack else '',
                    '<b>\n🛡Броня:           </b>{}'.format(self.stats.armor) if self.stats.armor else '',
                    '<b>\n💪Сила:              </b>{}'.format(self.stats.power) if self.stats.power else '',
                    '<b>\n🔫Меткость:     </b>{}'.format(self.stats.accuracy) if self.stats.accuracy else '',
                    '<b>\n🗣Харизма:       </b>{}'.format(self.stats.oratory) if self.stats.oratory else '',
                    '<b>\n🤸🏽‍♂️Ловкость:      </b>{}'.format(self.stats.agility) if self.stats.agility else '',
                    '<b>\n🔋Выносливость:    </b>{}'.format(self.stats.stamina) if self.stats.stamina else '',
                    '<b>\n\n🗡Успешные рейды: </b>{}'.format(self.raids) if self.raids else '',
                    '<b>\n🔧Исследования: </b>{}'.format(self.building) if self.building else '',
                    '<b>\n⚙️Карма: </b>{}'.format(self.karma) if self.karma else '')

    def __repr__(self):
        return '{} Date:</b>{}{}{}{}{}{}{}{}{}{}{}' \
            .format(self.username, self.nic,
                    'Squad: {}'.format(self.squad), self.stats.time.isoformat(' ', 'minutes'),
                    ' Hp: {}'.format(self.stats.hp),
                    ' Attack: {}'.format(self.stats.attack),
                    ' Armor: {}'.format(self.stats.armor),
                    ' Power: {}'.format(self.stats.power),
                    ' Accuracy: {}'.format(self.stats.accuracy),
                    ' Oratory: {}'.format(self.stats.oratory),
                    ' Agility: {}'.format(self.stats.agility),
                    ' Raids: {}'.format(self.raids),
                    ' Building: {}'.format(self.building),
                    ' Karma: {}'.format(self.karma))

    def choose_text_by_sex(self, male_text, female_text):
        return male_text if self.settings == 'male' else female_text

import telegram as telega
from ww6StatBotUtils import MessageManager
from ww6StatBotPin import power

class NightPin:
    loc_icons = {5: '📦', 9: '🕳', 12: '💊', 16: '🍗', 20: '🔹', 24: '❤️',
                 28: '💡', 32: '💾', 38: '🔩', 46: '🔗'}

    def __init__(self, message_manager:MessageManager):
        self.message_manager = message_manager
        self.players_all = set()
        self.players_unknown = []
        self.players_going = []
        self.players_onkm = []
        self.players_declined = []
        self.km = -1
        self.active = False
        self.masterpins = {}

    def open(self, km):
        self.km = km
        self.active = True

    def close(self):
        self.players_all.clear()
        self.players_unknown.clear()
        self.players_going.clear()
        self.players_onkm.clear()
        self.players_declined.clear()
        self.km = -1
        self.active = False

    def add(self, players):

        self.players_unknown.extend(list(set(players)))
        self.players_all = self.players_all.union(set(players))
        self.update_masterpins()

    def set_going(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_onkm:
            self.players_onkm.remove(player)
        if player in self.players_declined:
            self.players_declined.remove(player)
        if player not in self.players_going:
            self.players_going.append(player)
        self.update_masterpins()

    def set_declined(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_onkm:
            self.players_onkm.remove(player)
        if player in self.players_going:
            self.players_going.remove(player)
        if player not in self.players_declined:
            self.players_declined.append(player)
        self.update_masterpins()

    def set_onkm(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_declined:
            self.players_declined.remove(player)
        if player in self.players_going:
            self.players_going.remove(player)
        if player not in self.players_onkm:
            self.players_onkm.append(player)
        self.update_masterpins()

    def text_km(self):
        return "{}{} км".format(self.km, self.loc_icons[self.km] if self.km in self.loc_icons.keys() else "")

    def player_status(self, player, short=False):
        status = "Нет задания 🚫" if not short else "⭕️"
        if player in self.players_unknown:
            status = "Задание не принято ⏰" if not short else "⏰️"
        elif player in self.players_going:
            status = "Задание в процессе 🐌" if not short else "🐌"
        elif player in self.players_declined:
            status = "Задание отклонено ❌" if not short else "❌️"
        elif player in self.players_onkm:
            status = "Задание выполнено 🏕️" if not short else "🏕️️"
        return "Текущий статус выполнения задания по пину:\n<b>{}</b>".format(status) if not short else  status

    def get_message(self, player=None):
        if self.active:
            return "Привет!\nТебе пришел ночной пин\nВыдвигайся на <b>{0}</b>\nНе забудь нажать " \
                   "/npin_accept прямо сейчас, и скинуть 📟Пип-бой когда доберешься до <b>{0}</b>\n\n" \
                   "Для отказа нажми /npin_decline \nПодробности в /help_npin \n{1}".format(
                self.text_km(), self.player_status(player) if player else "")
        else:
            return "Ночной пин сейчас не активен"

    def masterpin_text(self):
        return "Ночной пин: <b>{}</b>\nПока не отметились (<b>{}</b>): {}\nУже вышли (<b>{}</b>)[<b>{}</b>]: {}\n" \
               "Пришли (<b>{}</b>)[<b>{}</b>]: {}\nНе пошли (<b>{}</b>): {}\n\nВсего: <b>{}</b>".format(
                    self.text_km(),
                    len(self.players_unknown), " ".join(['@' + pl.username for pl in self.players_unknown]),
                    len(self.players_going), sum(map(power, self.players_going)), " ".join(['@' + pl.username for pl in self.players_going]),
                    len(self.players_onkm), sum(map(power, self.players_onkm)), " ".join(['@' + pl.username for pl in self.players_onkm]),
                    len(self.players_declined), " ".join(['@' + pl.username for pl in self.players_declined]),
                    len(self.players_all))

    def set_masterpin(self, chat_id):
        mid = self.message_manager.bot.send_message(chat_id=chat_id, text=self.masterpin_text(), parse_mode='HTML').message_id
        self.masterpins[chat_id] = mid

    def update_masterpins(self):
        text = self.masterpin_text()
        for chat_id, mid in self.masterpins.items():
            try:
                self.message_manager.update_msg(timeout=2, chat_id=chat_id, message_id=mid, text=text,
                                                parse_mode='HTML')
            except telega.TelegramError as e:
                pass  # print(e.message)

import time
import datetime
import threading
import telegram as telega
from ww6StatBotPlayer import PlayerSettings, Player


class Notificator:
    def __init__(self, players :dict, bot:telega.Bot):
        """we assume that settings.notif_time is equal for all players and players is not empty"""
        self.players = players
        self.bot = bot
        dt, t = self._next_time()
        threading.Timer(dt, self.notify, args=[t]).start()

    def _next_time(self):
        now = datetime.datetime.now()
        arr = []
        player0 = [p for p in self.players.values()][0]
        for t in player0.settings.notif_time:
            h, m = [int(x) for x in t.split(':')]
            call_time = datetime.datetime(now.year, now.month, now.day, h, m)
            if now - call_time > datetime.timedelta(microseconds=-1):
                call_time = call_time + datetime.timedelta(days=1, seconds=-1)
            dt = (call_time - now).seconds
            if dt == 0:
                dt = 1000000
            arr.append((dt, t))
        return min(arr)

    def notify(self, key):
        player0 = [p for p in self.players.values()][0]
        i = player0.settings.notif_time.index(key)
        for pl in self.players.values():
            if pl.settings.notifications[key]:
                time.sleep(1./50)
                female = pl.settings.sex == 'female'
                msg = ""
                if i % 3 == 0:
                    msg = "Скоро рейд! Ты уже выш{}?".format("ла" if female else "ел")
                elif i % 3 == 1:
                    msg = "Скоро рейд! Ты уже отметил{} в пине?".format("ась" if female else "ся")
                else:
                    msg = "Недавно был рейд. Ты обновил{} профиль?".format("а" if female else "")
                try:
                    self.bot.sendMessage(chat_id=pl.chatid, text=msg)
                except:
                    pass

        dt, t = self._next_time()
        threading.Timer(dt, self.notify, args=[t]).start()

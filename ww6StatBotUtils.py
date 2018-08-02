import time
import telegram as telega
from telegram.ext import messagequeue as mq
import threading


class MessageManager:
    #  see https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits
    def __init__(self, bot: telega.Bot, is_queued_def=True, mqueue=None, timer=None):
        self.bot = bot
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()
        self._timer = timer or Timer()
        self._timer.add(self.run)
        self._timer.start()
        self._updates = {}
        self._lock = threading.RLock()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except:
            pass

    @mq.queuedmessage
    def send_message(self, callback: callable = None, callbackargs=None, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments"""
        try:
            return self.bot.send_message(*args, **kwargs)
        except telega.TelegramError as e:
            if callback:
                callback(e, callbackargs)
        except:
            pass

    def send_split(self, text, chat_id, lines_num=50, disable_web_page_preview=True):
        split = text.split('\n')
        for i in range(0, len(split), lines_num):
            time.sleep(1. / 30)
            self.send_message(chat_id=chat_id, text='\n'.join(split[i:min(i + lines_num, len(split))]), parse_mode='HTML',
                              disable_web_page_preview=disable_web_page_preview)

    def pin(self, chat_id, text, uid):
        mid = 0
        try:
            mid = self.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        except:
            pass
        time.sleep(0.5)
        if not mid:
            self.send_message(chat_id=uid, text="Не удалось доставить сообщение")
            return
        try:
            self.bot.pinChatMessage(chat_id=chat_id, message_id=mid)
        except:
            self.send_message(chat_id=uid, text="Я не смог запинить((")
            return
        self.send_message(chat_id=uid, text="Готово\nСообщение в пине")

    def update_msg(self, *args, **kwargs):
        with self._lock:
            self._updates[(kwargs['chat_id'], kwargs['message_id'])] = (args, kwargs)

    def run(self):
        ups = []
        with self._lock:
            ups = list(self._updates.values())
            self._updates.clear()
        for up in ups:
            self._update_msg(*up[0], **up[1])

    @mq.queuedmessage
    def _update_msg(self, *args, **kwargs):
        try:
            return self.bot.edit_message_text(*args, **kwargs)
        except:
            pass


class Timer:
    """one can add tascks but don't delete them, tasks arguments are not supported"""
    def __init__(self, interval=2):
        self.interval = interval
        self._thread = threading.Thread(target=self._loop)
        self._lock = threading.RLock()
        self.tasks = {}
        self.rate = {}
        self._goone = True
        self.ticks = 0
        self.ind = 0

    def add(self, task:callable, rate=1):
        with self._lock:
            self.tasks[self.ind] = task
            self.rate[self.ind] = rate
            self.ind += 1
        return self.ind - 1

    def start(self):
        if not self._thread.is_alive():
            with self._lock:
                self._thread = threading.Thread(target=self._loop)
                self._goone = True
                self.ticks = 0
                self._thread.start()

    def stop(self):
        with self._lock:
            goone = False
            self._thread.join()

    def delete(self, ind):
        try:
            del(self.tasks[ind])
            del(self.rate[ind])
        except:
            pass


    def _loop(self):
        while self._goone:
            t = time.time()
            interval = max(self.interval - (time.time() - t), 0.01)
            for ind, task in list(self.tasks.items()):
                if self.ticks % self.rate[ind] == 0:
                    try:
                        task()
                    except:
                        pass
            with self._lock:
                self.ticks += 1
            time.sleep(interval)

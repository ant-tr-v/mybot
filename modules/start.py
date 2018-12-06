import telegram
from telegram.ext import CommandHandler, Dispatcher

from .base import BaseStatBotModule


class StartStatBotModule(BaseStatBotModule):
    """
    responds to /start command
    """
    module_name = 'start'


    def __init__(self, dispatcher: Dispatcher=None):
        self.add_handler(CommandHandler('start', self._start))
        super().__init__(dispatcher)

    def _start(self, bot: telegram.Bot, update: telegram.Update):
        message = update.message
        message_text = (
            "Привет, давай знакомиться!\n"
            "Перейди в игру, открой 📟 Пип-бой, "
            "нажми команду <code>/me</code> внизу и перешли мне сообщение с полным профилем"
        )
        markup = telegram.InlineKeyboardMarkup(
            [[telegram.InlineKeyboardButton(text="Перейти в игру", url="https://t.me/WastelandWarsBot")]])
        bot.send_message(chat_id=message.chat_id, text=message_text, parse_mode='HTML', reply_markup=markup)

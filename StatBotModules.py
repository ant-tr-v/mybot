import telegram
from telegram.ext import Dispatcher, CommandHandler


class BaseStatBotModule(object):
    """
    Basic class for bot modules.
    All modules must be subclasses of this class
    """
    module_name = None

    def __str__(self) -> str:
        return self.module_name

    def __init__(self, dispatcher: Dispatcher):
        pass


class StartStatBotModule(BaseStatBotModule):
    """
    responds to /start command
    """
    module_name = 'Start'

    def __init__(self, dispatcher: Dispatcher):
        super().__init__(dispatcher)
        handler = CommandHandler('start', self._start)
        dispatcher.add_handler(handler)

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

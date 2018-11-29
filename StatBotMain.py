from telegram.ext import Updater

from StatBotModules import StartStatBotModule
from config import CurrentConfig


class StatBot:
    def __init__(self):
        # initializing Updater
        tg_request_kwargs = {'proxy_url': CurrentConfig.TG_PROXY_URL, 'urllib3_proxy_kwargs':
            {'username': CurrentConfig.TG_PROXY_USERNAME, 'password': CurrentConfig.TG_PROXY_PASSWORD}
                             } if CurrentConfig.TG_USE_PROXY else None
        self.updater = Updater(token=CurrentConfig.TG_TOKEN, request_kwargs=tg_request_kwargs)

        # initializing Modules
        modules = [StartStatBotModule]

        self.modules = []
        for module in modules:
            self.modules.append(module(self.updater.dispatcher))

        print('Active modules:', ' '.join(map(str, self.modules)))

    def start(self):
        self.updater.bot.send_message(chat_id=273060432, text='started')
        self.updater.start_polling(clean=True)
        self.updater.idle()


if __name__ == '__main__':
    statbot = StatBot()
    statbot.start()

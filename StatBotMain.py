import logging
from urllib.parse import urlparse

from telegram.ext import Updater

from config import settings
from modules import StartStatBotModule


class StatBot:

    def _get_request_kwargs(self) -> dict:
        '''Returns request_kwargs dictionary if proxy used in settngs'''
        tg_request_kwargs = None
        if settings.TG_PROXY_URL:
            proxy_url = settings.TG_PROXY_URL
            urllib3_proxy_kwargs = {}
            parser = urlparse(proxy_url)
            if parser.username:
                # remove username and password from url
                proxy_url = parser._replace(netloc=f'{parser.hostname}:{parser.port}').geturl()
                urllib3_proxy_kwargs = {
                    'username': parser.username,
                    'password': parser.password
                }
            tg_request_kwargs = {
                'proxy_url': proxy_url,
                'urllib3_proxy_kwargs': urllib3_proxy_kwargs
            }
            self.logger.info('Proxy used: %s', proxy_url)
        return tg_request_kwargs

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # initializing Updater
        tg_request_kwargs = self._get_request_kwargs()
        self.updater = Updater(token=settings.TG_TOKEN, request_kwargs=tg_request_kwargs)

        # initializing Modules
        modules = [StartStatBotModule]

        self.modules = []
        for Module in modules:
            module = Module()
            module.set_handlers(self.updater.dispatcher)
            self.modules.append(module)

        self.logger.info('Active modules: %s', ', '.join(map(str, self.modules)))

    def start(self):
        self.logger.info('%s started', self.updater.bot.name)
        self.updater.bot.send_message(chat_id=settings.ADMIN_CHAT_ID, text='started')
        self.updater.start_polling(clean=True)
        self.updater.idle()


if __name__ == '__main__':
    statbot = StatBot()
    statbot.start()

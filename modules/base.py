import logging

from telegram.ext import Dispatcher, Handler


class BaseStatBotModule(object):
    """
    Basic class for bot modules.
    All modules must be subclasses of this class
    """
    module_name = None
    group = 10
    handler_list = []

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def add_handler(self, handler: Handler):
        self.handler_list.append(handler)

    def set_handlers(self, dispatcher: Dispatcher):
        if not self.handler_list:
            raise ValueError('You must set at least one handler')
        for handler in self.handler_list:
            dispatcher.add_handler(handler, group=self.group)

    def __str__(self) -> str:
        return self.module_name

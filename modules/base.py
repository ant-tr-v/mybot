import logging

from telegram.ext import Dispatcher, Handler


class BaseStatBotModule(object):
    """
    Basic class for bot modules.
    All modules must be subclasses of this class
    """
    module_name = None
    group = 10
    _handler_list = []

    def __init__(self, dispatcher: Dispatcher=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        if dispatcher:
            self.set_handlers(dispatcher)

    def add_handler(self, handler: Handler):
        self._handler_list.append(handler)

    def set_handlers(self, dispatcher: Dispatcher):
        if not self._handler_list:
            raise ValueError('You must set at least one handler')
        for handler in self._handler_list:
            dispatcher.add_handler(handler, group=self.group)

    def __str__(self) -> str:
        return self.module_name

import datetime

import telegram
from telegram import Bot, Update
from telegram.ext import Dispatcher, Filters, MessageHandler

from models import TelegramChat, TelegramUser, database

from .base import BaseStatBotModule


class ActivityBotModule(BaseStatBotModule):
    """
    Tracks new users, chats, and user`s activity
    """
    module_name = 'activity'
    group = 0

    def __init__(self, dispatcher: Dispatcher=None):
        self.add_handler(MessageHandler(Filters.all, self._write_activity))
        super().__init__(dispatcher)

    def _write_activity(self, bot: Bot, update: Update):
        user_data = update.effective_user
        chat_data = update.effective_chat
        with database:
            user, created = TelegramUser.get_or_create(user_id=user_data.id)
            if created:
                self.logger.info('New user: #%s @%s', user_data.id,
                                 user_data.username)
            else:
                for attr in ('username', 'first_name', 'last_name'):
                    old = getattr(user, attr)
                    new = getattr(user_data, attr)
                    if old != new:
                        self.logger.info('User #%s @%s change %s: %s → %s',
                                         user_data.id, user.username, attr,
                                         old, new)
            user.username = user_data.username
            user.first_name = user_data.first_name
            user.last_name = user_data.last_name
            user.last_seen_date = datetime.datetime.now()
            if chat_data.type == 'private':
                user.chat_id = chat_data.id
            user.save()

            if chat_data.type == 'private':
                return
            chat, created = TelegramChat.get_or_create(
                chat_id=chat_data.id, chat_type=chat_data.type)
            if created:
                self.logger.info('New chat: %s', chat_data.title)
                chat.title = chat_data.title
                chat.save()
            elif chat.title != chat_data.title:
                self.logger.info('Chat renamed: %s → %s', chat.title,
                                 chat_data.title)
                chat.title = chat_data.title
                chat.save()

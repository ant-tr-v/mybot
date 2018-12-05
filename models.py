import datetime
import os

import peewee
from playhouse.db_url import connect

from config import settings

# Connect to the database URL defined in the environment
database = connect(settings.DATABASE_URL)


class BaseModel(peewee.Model):
    class Meta:
        database = database


class TelegramUser(BaseModel):
    user_id = peewee.IntegerField(
        null=False, index=True, unique=True, primary_key=True)
    chat_id = peewee.IntegerField(null=True, unique=True)

    username = peewee.CharField(max_length=32, null=True, index=True)
    first_name = peewee.CharField(max_length=255, null=True)
    last_name = peewee.CharField(max_length=255, null=True)

    is_admin = peewee.BooleanField(default=False)
    is_banned = peewee.BooleanField(default=False)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_seen_date = peewee.DateTimeField(null=True)

    def __str__(self) -> str:
        if self.username:
            return f'@{self.username}'
        return f'#{self.user_id}'

    class Meta:
        only_save_dirty = True


class TelegramChat(BaseModel):
    chat_id = peewee.IntegerField(
        null=False, index=True, unique=True, primary_key=True)
    chat_type = peewee.CharField(
        max_length=10,
        choices=(('CHANNEL', 'channel'), ('GROUP', 'group'), ('SUPERGROUP',
                                                              'supergroup')))
    title = peewee.CharField(max_length=255, null=True)
    shortname = peewee.CharField(max_length=32, null=True, index=True)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True


with database:
    database.create_tables([
        TelegramUser, TelegramChat
    ])

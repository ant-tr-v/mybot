import datetime
import peewee

from .baseModel import BaseModel


class TelegramChat(BaseModel):
    chat_id = peewee.BigIntegerField(
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

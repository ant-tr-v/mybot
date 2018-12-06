import datetime
import peewee

from .baseModel import BaseModel


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

from .baseModel import BaseModel, database
from .telegramUser import TelegramUser
from .telegramChat import TelegramChat

with database:
    database.create_tables([
        TelegramUser, TelegramChat
    ])

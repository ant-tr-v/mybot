import peewee
from playhouse.db_url import connect

from config import settings

# Connect to the database URL defined in the environment
database = connect(settings.DATABASE_URL)


class BaseModel(peewee.Model):
    class Meta:
        database = database

# coding: utf-8
import logging.config
import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
BASEDIR = os.path.dirname(__file__)


class ImproperlyConfigured(Exception):
    """Something is somehow improperly configured"""
    pass


class Config(object):
    """Base class for app configuration"""
    DEBUG = False
    TESTING = False

    DATABASE_URL = os.getenv('DATABASE_URL',
                             'sqlite:///' + os.path.join(BASEDIR, 'db.sqlite'))

    TG_TOKEN = os.getenv('TG_TOKEN')

    TG_PROXY_URL = os.getenv('TG_PROXY_URL')

    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '273060432')

    LOG_LEVEL = 'INFO'

    @property
    def LOGGING_CONFIG(self):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format':
                    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': self.LOG_LEVEL,
                    'propagate': True
                }
            }
        }

    def __init__(self):
        if not self.TG_TOKEN:
            raise ImproperlyConfigured(
                'You must set TG_TOKEN enviroment variable')
        try:
            self.ADMIN_CHAT_ID = int(self.ADMIN_CHAT_ID)
        except ValueError:
            raise ImproperlyConfigured('ADMIN_CHAT_ID must be integer')
        self.BASEDIR = BASEDIR
        logging.config.dictConfig(self.LOGGING_CONFIG)


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.environ.get('TEST_DATABASE_URI') or 'sqlite://'


class ProductionConfig(Config):
    DEBUG = False

    @property
    def LOGGING_CONFIG(self):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format':
                    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(BASEDIR, 'logs', 'bot.log'),
                    'mode': 'a',
                    'maxBytes': 10485760,  # 1M
                    'backupCount': 5,
                },
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': self.LOG_LEVEL,
                    'propagate': True
                }
            }
        }


# При инициализации бота должно указываться название запускаемой конфигурации,
#   либо по умолчанию будет режим dev
_config_relation = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

ConfigClass = _config_relation[os.environ.get('BOT_CONFIG', 'default')]
settings = ConfigClass()

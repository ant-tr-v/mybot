# coding: utf-8
import logging.config
import os

BASEDIR = os.path.dirname(__file__)

log_ini = 'logging.ini'
if os.path.exists(log_ini):
    logging.config.fileConfig(log_ini)


class Config(object):
    DEBUG = False
    TESTING = False

    PEEWEE_DATABASE_URI = os.getenv('DATABASE_URI',
                                    'sqlite:///' + os.path.join(BASEDIR, 'db.sqlite'))

    TG_TOKEN = os.getenv('TG_TOKEN')
    TG_BOT_NAME = os.getenv('TG_BOT_NAME')

    TG_PROXY_URL = os.getenv('TG_PROXY_URL')
    TG_PROXY_USERNAME = os.getenv('TG_PROXY_USERNAME')
    TG_PROXY_PASSWORD = os.getenv('TG_PROXY_PASSWORD')
    TG_USE_PROXY = TG_PROXY_URL is not None

    RATELIMIT_CHAT_ID = os.getenv('RATELIMIT_CHAT_ID', '273060432')


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    PEEWEE_DATABASE_URI = os.environ.get('TEST_DATABASE_URI') or 'sqlite://'


class ProductionConfig(Config):
    DEBUG = False


# При инициализации бота должно указываться название запускаемой конфигурации,
#   либо по умолчанию будет режим dev
_config_relation = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': DevelopmentConfig
}

CurrentConfig = _config_relation[os.environ.get('BOT_CONFIG', 'default')]

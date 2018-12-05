"""This module code to convert old bot database to new one"""
import os
import sqlite3 as sql

from peewee import DoesNotExist

from models import TelegramChat, TelegramUser, database


def convert(master_db_path: str):
    master_connection = sql.connect(master_db_path)
    cursor = master_connection.cursor()

    database.connect()
    database.create_tables([
        TelegramUser,
    ])

    cursor.execute(
        'SELECT id as user_id, username, chatid as chat_id from users')
    user_list = [
        TelegramUser(user_id=user_id, username=username, chat_id=chat_id)
        for user_id, username, chat_id in cursor.fetchall()
    ]
    TelegramUser.bulk_create(user_list)

    cursor.execute('SELECT id FROM admins')
    for user_id in cursor.fetchall():
        try:
            user = TelegramUser.get_by_id(user_id)
        except DoesNotExist:
            pass
        else:
            user.is_admin = True
            user.save()
    
    cursor.execute('SELECT id FROM blacklist')
    for user_id in cursor.fetchall():
        try:
            user = TelegramUser.get_by_id(user_id)
        except DoesNotExist:
            pass
        else:
            user.is_banned = True
            user.save()
    
    cursor.execute(
        'SELECT chatid, name, short from squads')
    chat_list = [
        TelegramChat(chat_id=chatid, chat_type='supergroup', title=name, shortname=short)
        for chatid, name, short in cursor.fetchall()
    ]
    TelegramChat.bulk_create(chat_list)

    master_connection.close()
    database.close()

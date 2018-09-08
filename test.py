#!/usr/bin/env python3

import os
import sqlite3 as sql
import unittest
from unittest.mock import Mock, PropertyMock, patch

from telegram import User

from ww6StatBot import Bot
from ww6StatBotPlayer import Player


class TestBot(unittest.TestCase):
    db_path = 'test.sqlite'

    def setUp(self):
        '''
        Mock de_path and conn setup to avoid touching main database
        '''
        # Patch things
        patcher = patch.object(Bot, 'db_path', new_callable=PropertyMock, return_value=self.db_path)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Create bot instance
        self.bot = Bot()
        self.addCleanup(self.bot.stop)

        self.conn = sql.connect(self.db_path)
        self.addCleanup(self.conn.close)

    def get_test_player_data(self):
        user_id = 39395628
        username = 'BATC0H'
        nickname = '🔹BATCOH🔹'
        return user_id, username, nickname
    
    def add_player(self, user_id, username, nickname) -> Player:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO users(id, chatid, username) VALUES(?, ?, ?)",
                    (user_id, 321321, username))
        player = Player(cur, (user_id, 321321, username, nickname, "", [None, None, None, None, None]))

        self.bot.users[user_id] = player
        self.bot.usersbyname[username.lower()] = user_id

        return player

    def del_player(self, user_id):
        cur = self.conn.cursor()
        self.bot.ban(cur, user_id, False)
        self.conn.commit()

    def test_demand_squads(self):
        bot = self.bot
        
        # add squads
        chat_id = 123456789
        bot.squadnames['sq'] = 'Squad name'
        bot.squadids['sq'] = chat_id
        bot.squads_by_id[chat_id] = 'sq'

        chat_id = 987654321
        bot.squadnames['la'] = 'Los Angeles'
        bot.squadids['la'] = chat_id
        bot.squads_by_id[chat_id] = 'la'

        user_id, username, nickname = self.get_test_player_data()
        self.add_player(user_id, username, nickname)

        bot.admins.add(user_id)

        user = User(user_id, False, username, '', username)

        send_mock = Mock()
        bot.message_manager.send_message = send_mock

        text = '/echo Привет!'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True)
        self.assertEqual(sqs, [])
        self.assertEqual(msg, 'Привет!')

        text = '/echo sq'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True)
        self.assertEqual(sqs, None)
        self.assertEqual(msg, None)
        send_mock.assert_called()

        text = '/echo sq Привет!'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True)
        self.assertEqual(sqs, ['sq',])
        self.assertEqual(msg, 'Привет!')

        text = '/echo sq la Привет!'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True)
        self.assertEqual(sqs, ['sq', 'la'])
        self.assertEqual(msg, 'Привет!')

        text = '/echo sq la Привет!'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True, default_message="Пинпинпин")
        self.assertEqual(sqs, ['sq', 'la'])
        self.assertEqual(msg, 'Привет!')

        text = '/echo sq la'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True, default_message="Пинпинпин")
        self.assertEqual(sqs, ['sq', 'la'])
        self.assertEqual(msg, "Пинпинпин")

        text = '/echo sq la /autoping ls la'
        sqs, msg = bot.demand_squads(text, user, allow_empty_squads=True, default_message="Пинпинпин")
        self.assertEqual(sqs, ['sq', 'la'])
        self.assertEqual(msg, '/autoping ls la')

        # cleanup
        self.del_player(user_id)
        bot.admins = set()
        bot.squadnames = {}
        bot.squadids = {}
        bot.squads_by_id = {}
    
    def test_titles(self):
        bot = self.bot
        # add_user
        user_id, username, nickname = self.get_test_player_data()
        player = self.add_player(user_id, username, nickname)

        cur = self.conn.cursor()

        player.add_title(cur, 'Тестовое звание 1')
        self.conn.commit()
        self.assertEqual(len(player.titles), 1)
        self.assertEqual(player.titles[0], 'Тестовое звание 1')
        self.assertEqual(len(player.get_titles(cur)), 1)

        player.add_title(cur, 'Тестовое звание 2;')
        self.conn.commit()
        self.assertEqual(len(player.titles), 2)
        self.assertEqual(player.titles[1], 'Тестовое звание 2;')
        self.assertEqual(len(player.get_titles(cur)), 2)

        player.add_title(cur, 'очень тестовое звание 3⚙️⚙️⚙️')
        self.conn.commit()
        self.assertEqual(len(player.titles), 3)
        self.assertEqual(player.titles[2], 'очень тестовое звание 3⚙️⚙️⚙️')
        self.assertEqual(len(player.get_titles(cur)), 3)

        # del_title
        player.del_title(cur, 'Несуществующее звание')
        self.conn.commit()
        self.assertEqual(len(player.titles), 3)
        self.assertEqual(len(player.get_titles(cur)), 3)
        # TODO

        player.del_title(cur, 'Тестовое звание 2;')
        self.conn.commit()
        self.assertEqual(len(player.titles), 2)
        self.assertEqual(player.titles[0], 'Тестовое звание 1')
        self.assertEqual(player.titles[1], 'очень тестовое звание 3⚙️⚙️⚙️')
        self.assertEqual(len(player.get_titles(cur)), 2)

        # untitle
        player.clear_titles(cur)
        self.conn.commit()
        self.assertEqual(len(player.titles), 0)
        self.assertEqual(len(player.get_titles(cur)), 0)

        # del_user
        self.del_player(user_id)

    def tearDown(self):
        if os.path.isfile(self.db_path):
            os.remove(self.db_path)

if __name__ == '__main__':
    unittest.main()

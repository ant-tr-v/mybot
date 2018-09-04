#!/usr/bin/env python3

import os
import unittest
from ww6StatBot import Bot
from unittest.mock import patch, PropertyMock, Mock
from telegram import User

class TestBot(unittest.TestCase):
    db_path = 'test.sqlite'

    def setUp(self):
        # Patch things
        patcher = patch.object(Bot, 'db_path', new_callable=PropertyMock, return_value=self.db_path)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Create bot instance
        self.bot = Bot()
        # Patch send_message method
        self.addCleanup(self.bot.stop)
    
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

        class Player(object):
            id = None
            chatid = None
            username = None

        user_id = 123123
        chat_id = 321321
        user = User(user_id, False, 'Drobb', '', 'drobb')
        bot.users[user_id] = Player()
        bot.users[user_id].id = user_id
        bot.users[user_id].chatid = chat_id
        bot.users[user_id].username = 'drobb'
        bot.usersbyname['drobb'] = user_id
        bot.admins.add(user_id)

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

    def tearDown(self):
        if os.path.isfile(self.db_path):
            os.remove(self.db_path)

if __name__ == '__main__':
    unittest.main()
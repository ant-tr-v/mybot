#!/usr/bin/env python3

import os
import unittest

from ww6StatBotChat import Chat, ChatType
from ww6StatBotData import DataBox
from ww6StatBotPlayer import Player
from ww6StatBotSQL import SQLManager


class TestDataBox(unittest.TestCase):
    '''
    We need to test that good old `DataBox` public API does not breaks or changed
    '''
    db_path = 'test.sqlite'

    def setUp(self):
        self.sql_manager = SQLManager(self.db_path)
        self.data_box = DataBox(self.sql_manager)

    def tearDown(self):
        if os.path.isfile(self.db_path):
            os.remove(self.db_path)

    def get_test_player_data(self):
        uid = 39395628
        username = 'BATC0H'
        nickname = '🔹BATCOH🔹'
        return uid, username, nickname

    def get_test_chat_data(self):
        chat_id = -1001381472351
        name = 'test1'
        full_name = 'Очень тестовый чат'
        chat_type = ChatType.CHAT
        return chat_id, name, full_name, chat_type

    def test_player(self):
        uid, username, nickname = self.get_test_player_data()

        # add_player
        pl = self.data_box.add_player(uid, username, nickname)
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)

        # player
        pl = self.data_box.player(uid)
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)
        self.assertWarns(PendingDeprecationWarning)

        self.assertIsNone(self.data_box.player(273060432))

        # player_by_username
        pl = self.data_box.player_by_username(username)
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)
        self.assertWarns(PendingDeprecationWarning)

        self.assertIsNone(self.data_box.player_by_username('@ant_ant'))

        # all_players
        all_players = self.data_box.all_players()
        self.assertIsInstance(all_players, set)
        self.assertEqual(len(all_players), 1)
        pl = all_players.pop()
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)

        # all_player_usernames
        all_players = self.data_box.all_player_usernames()
        self.assertIsInstance(all_players, set)
        self.assertEqual(len(all_players), 1)
        self.assertEqual(all_players.pop(), username.lower())

        # players_by_username
        test_str = '{} {}'.format(username, '@ant_ant')
        found, not_found = self.data_box.players_by_username(test_str)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(not_found), 1)
        pl = found.pop()
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, '@ant_ant')

        found, not_found = self.data_box.players_by_username(
            test_str, parse_all=False)
        self.assertEqual(len(found), 1)
        self.assertIsInstance(not_found, str)
        self.assertEqual(not_found, '@ant_ant')
        pl = found.pop()
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)

        found, not_found = self.data_box.players_by_username(
            test_str, offset=1)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 0)
        self.assertEqual(len(not_found), 1)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, '@ant_ant')

        test_str = 'test {} {}'.format(username, '@ant_ant')
        found, not_found = self.data_box.players_by_username(
            test_str, offset=1)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(not_found), 1)
        pl = found.pop()
        self.assertIsInstance(pl, Player)
        self.assertEqual(pl.uid, uid)
        self.assertEqual(pl.username, username)
        self.assertEqual(pl.nic, nickname)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, '@ant_ant')

        # del_player
        self.data_box.del_player(pl)
        all_players = self.data_box.all_player_usernames()
        self.assertEqual(len(all_players), 0)

    def test_chats(self):
        # TODO: more coverage
        chat_id, name, full_name, chat_type = self.get_test_chat_data()
        chat = self.data_box.add_chat(chat_id, name, full_name, chat_type)

        self.assertIsInstance(chat, Chat)
        self.assertEqual(chat.chat_id, chat_id)
        self.assertEqual(chat.name, name)
        self.assertEqual(chat.title, full_name)
        self.assertEqual(chat.chat_type, chat_type)

        # chats_by_name
        test_str = '{} {}'.format(name, 'test')
        found, not_found = self.data_box.chats_by_name(test_str)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(not_found), 1)
        chat = found.pop()
        self.assertIsInstance(chat, Chat)
        self.assertEqual(chat.chat_id, chat_id)
        self.assertEqual(chat.name, name)
        self.assertEqual(chat.title, full_name)
        self.assertEqual(chat.chat_type, chat_type)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, 'test')

        found, not_found = self.data_box.chats_by_name(
            test_str, parse_all=False)
        self.assertEqual(len(found), 1)
        self.assertIsInstance(not_found, str)
        self.assertEqual(not_found, 'test')
        chat = found.pop()
        self.assertIsInstance(chat, Chat)
        self.assertEqual(chat.chat_id, chat_id)
        self.assertEqual(chat.name, name)
        self.assertEqual(chat.title, full_name)
        self.assertEqual(chat.chat_type, chat_type)

        found, not_found = self.data_box.chats_by_name(test_str, offset=1)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 0)
        self.assertEqual(len(not_found), 1)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, 'test')

        test_str = 'test {} {}'.format(name, 'test22')
        found, not_found = self.data_box.chats_by_name(test_str, offset=1)
        self.assertIsInstance(found, set)
        self.assertIsInstance(not_found, set)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(not_found), 1)
        chat = found.pop()
        self.assertIsInstance(chat, Chat)
        self.assertEqual(chat.chat_id, chat_id)
        self.assertEqual(chat.name, name)
        self.assertEqual(chat.title, full_name)
        self.assertEqual(chat.chat_type, chat_type)
        nf = not_found.pop()
        self.assertIsInstance(nf, str)
        self.assertEqual(nf, 'test22')

    def test_blacklist(self):
        uid, username, nickname = self.get_test_player_data()
        pl = self.data_box.add_player(uid, username, nickname)

        self.assertFalse(self.data_box.uid_in_blacklist(uid))
        self.data_box.add_blacklist(pl)
        self.assertTrue(self.data_box.uid_in_blacklist(uid))

        self.data_box.del_player(pl)

    def test_admins(self):
        uid, username, nickname = self.get_test_player_data()
        pl = self.data_box.add_player(uid, username, nickname)
        self.assertFalse(self.data_box.uid_is_admin(uid))
        self.assertFalse(self.data_box.player_is_admin(pl))

        self.data_box.add_admin(pl)
        self.assertTrue(self.data_box.uid_is_admin(uid))
        self.assertTrue(self.data_box.player_is_admin(pl))

        self.data_box.del_admin(pl)
        self.assertFalse(self.data_box.uid_is_admin(uid))
        self.assertFalse(self.data_box.player_is_admin(pl))

        self.data_box.del_player(pl)

    def test_masters(self):
        uid, username, nickname = self.get_test_player_data()
        pl = self.data_box.add_player(uid, username, nickname)

        self.assertFalse(self.data_box.player_has_rights(pl))
        self.data_box.add_admin(pl)
        self.assertTrue(self.data_box.player_has_rights(pl))

        chat = Chat()
        self.data_box.del_admin(pl)
        self.assertFalse(self.data_box.player_has_rights(pl, chat))
        chat.masters.add(pl)
        self.assertTrue(self.data_box.player_has_rights(pl, chat))

        self.data_box.del_player(pl)


if __name__ == '__main__':
    unittest.main()

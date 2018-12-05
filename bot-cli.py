#!/usr/bin/env python
'''This module contains command line tools'''
import argparse
import logging
import os
import sys


class BotCliRunner(object):
    def __init__(self):
        usage = (
            f'{sys.argv[0]} <command> [<args>]\n'
            'Currently available commands are:\n'
            '    runbot     Runs statbot in long pooling mode\n'
            '    convertdb  Converts sqlite databse from 1.x version to 2.0')
        parser = argparse.ArgumentParser(
            description='Stat Bot command line interface', usage=usage)
        parser.add_argument('command', help='Command to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def runbot(self):
        from StatBotMain import StatBot
        statbot = StatBot()
        statbot.start()

    @staticmethod
    def _is_valid_file(parser, arg):
        if not os.path.exists(arg):
            parser.error(f'The file {arg} does not exist!')
        else:
            return os.path.realpath(arg)

    def convertdb(self):
        parser = argparse.ArgumentParser(
            description='Converts sqlite databse from 1.x version to 2.0')
        parser.add_argument(
            'db_path',
            help='Path to old sqlite database file',
            type=lambda x: self._is_valid_file(parser, x))
        args = parser.parse_args(sys.argv[2:])

        from utils.convert import convert
        convert(args.db_path)


if __name__ == '__main__':
    BotCliRunner()

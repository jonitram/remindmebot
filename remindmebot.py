#!/usr/bin/env python3
import asyncio
from dateparser import parse
from dateparser.search import search_dates
import datetime
import discord
import os
import pickle
import re

### GLOBAL VARIABLES ###

# api tokens
discord_token=None

# the text file that the tokens are stored in
tokens_file = "tokens.txt"
# pickle file where persistent reminders are stored in
save_file = "saved_reminders.pkl"

# message prefixes the bot will respond to
# index [0] is the default
bot_prefixes = ['rm','remind']

# list of emojis for reaction options
emojis = ['🇦','🇧','🇨','🇩','🇪']

commands = ['clear','delete','help','reminders','restart']
# parallel arrays; need to match indices
help_messages = [' \"clear\" : Deletes commands issued to the bot and messages sent by the bot in the current channel (Up to 500 messages back).',
                 ' \"delete <Reminder>/all\" : Deletes the specified reminder / all of your reminders.'
                     '\nYou can specify a reminder using its reminder message or its number on the \"reminders\" list',
                 ' \"help\" : Sends the help message.',
                 ' \"reminders\" : Sends a list of your active reminders.',
                 ' \"restart\" : Restarts and updates the bot.']

# in the order they appear
confirmation_options = ['Delete this reminder (Will also delete both messages).',
                        'Delete both messages.',
                        'Delete this message.',
                        'Delete the message that created this reminder.']

# Reminder -> asyncio task running the reminder
reminder_tasks = {}
# user_id -> Reminder[]
user_reminders = {}

### BUILDING MESSAGES ###

def build_help_message(mention):
    result = mention + ' Create a reminder by using any message prefix with a specific reminder message and a specific time.'
    result += 'A reminder can be created without a message and a reminder can be created without a time (defaults to in 1 day).'
    result += '\nEx: \"remindme test in 2 hours\" will create a reminder in 2 hours with the reminder message \"test\".'
    result += '\nHere is a list of message prefixes the bot will respond: '
    for i in range(len(bot_prefixes)-1):
        result += '\"' + bot_prefixes[i] + '\", '
    result += 'and \"' + bot_prefixes[len(bot_prefixes)-1] + '\".'
    result += '\nAs long as the first word in your message contains a prefix, the bot will respond.'
    result += '\nHere is a list of available commands. If you would like to learn more about a command, please react to this message with that command\'s corresponding reaction:'
    result += '\n' + build_reaction_options(commands)
    return result

def build_reaction_options(options):
    result = ''
    for i in range(len(options)):
        result += '| ' + emojis[i] +' - ' + options[i] + ' '
    result += '|'
    return result
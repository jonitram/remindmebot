#!/usr/bin/env python3
import asyncio
import discord
from dateparser.search import search_dates
import dateparser
import datetime
import re

# api tokens
discord_token=None

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

# a list of message prefixes the bot will respond to
# index [0] is the default
command_prefixes = ['rm','rm!','remindme!','!rm','!remindme']

reminder_tasks = {}
user_reminders = {}

commands = ['help','reminders','delete','deleteall']

# the discord client
help_activity = discord.Activity(name='\"' + command_prefixes[0] + ' help\" for help',type=discord.ActivityType.playing)
client = discord.Client(activity=help_activity)

# initialization stuff
# sets up tokens
def setup_tokens(filename):
    global discord_token
    tokens = open(filename, "r")
    discord_token = tokens.readline().rstrip()
    tokens.close()
    return

@client.event
async def on_message(message):
    for prefix in command_prefixes:
        if message.content.lower().startswith(prefix + ' '):
            parameters = message.content.replace(prefix, '', 1).lower().split()
            if len(parameters) == 0:
                if parameters[0] == 'help':
                    # help message
                    return
                elif parameters[0] == 'reminders':
                    # display all reminders for that user
                    return
                elif parameters[0] == 'deleteall':
                    # delete all reminders
                    return
            elif parameters[0] == 'delete':
                # delete reminder
                return
            else:
                # assume its reminder otherwise
                asyncio.create_task(create_reminder(message))
                # async create task send confirmation
            return
    # if auther == bot and begins with confirmation message
    # attatch reactions
    return

async def create_reminder(message):
    global reminder_tasks, user_reminders
    extracted_times = search_dates(message.content, settings={'PREFER_DATES_FROM' : 'future', 'PREFER_DAY_OF_MONTH' : 'first', 'RELATIVE_BASE' : message.created_at})
    delimiters = command_prefixes
    for i in range(len(extracted_times)):
        delimiters.append(extracted_times[i][0])
    regex_pattern = '|'.join(map(re.escape, delimiters))
    reminder_messages = re.split(regex_pattern, message.content)
    reminder_messages = [reminder_message.strip() for reminder_message in reminder_messages if reminder_message != '']
    print(reminder_messages)
    # for i in range(len(extracted_times)):
        
    #     reminder_times.append(extracted_times[i][1])
    # for i in range(len(reminder_times)):
    #     # create reminder for each thing
    #     if message.id not in reminders.keys():
    #         reminders.update({message.id : []})
    #     temp = reminders.get(message.id)
    #     if i in range(len(reminder_messages)):
    #         temp.append(asyncio.create_task(run_reminder(message, reminder_times[i][1], reminder_messages[i])))
    #     else:
    #         temp.append(asyncio.create_task(run_reminder(message, reminder_times[i][1], '')))
    #     reminders.update({message.id : temp})
    #     return

async def run_reminder(message, reminder_time, reminder_message):
    delay = reminder_time - datetime.datetime.now()
    await asyncio.sleep(delay.total_seconds())
    print('done')
    return

# main function
def main():
    setup_tokens(tokensfile)
    # build_help_message()
    client.run(discord_token)

if __name__ == "__main__": main()
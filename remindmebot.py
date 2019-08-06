#!/usr/bin/env python3
import asyncio
import discord
from dateparser.search import search_dates
from dateparser import parse
from collections import defaultdict
import datetime
import re

# api tokens
discord_token=None

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

# a list of message prefixes the bot will respond to
# index [0] is the default
command_prefixes = ['rm','remindme','rm!','remindme!','!rm','!remindme']

reminder_tasks = {}
# Reminder -> background sleep task
user_reminders = defaultdict(list)
# user -> []Reminders

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

class Reminder:
    def __init__(self, user, message, channel, guild, time=parse("in 1 day"), info=''):
        self.user = user
        self.message = message
        self.channel = channel
        self.guild = guild
        self.time = time
        self.info = info
    
    # for use as a dictionary key
    def __hash__(self):
        return hash(self.message, self.time, self.info)
    
    def __eq__(self, other):
        return (self.message, self.time, self.info) == (self.message, self.time, self.info)
    
    def __ne__(self, other):
        return not(self == other)

    # for debugging
    def to_string(self):
        print('User Name: {0} Message ID: {1} Channel ID: {2} Guild ID: {3} Time: {4} Info: {5}'.format(self.user.name,self.message.id,self.channel.id,self.guild.id,self.time.strftime("%m/%d/%Y, %H:%M:%S"),self.info))

@client.event
async def on_message(message):
    for prefix in command_prefixes:
        if message.content.lower().startswith(prefix + ' '):
            parameters = message.content.lower().replace(prefix,'',1).split()
            if len(parameters) == 1:
                if parameters[0] == 'help':
                    # help message
                    return
                elif parameters[0] == 'reminders':
                    # display all reminders for that user
                    return
                elif parameters[0] == 'deleteall':
                    # delete all reminders
                    return
                elif parameters[0] == 'clear':
                    # clear
                    return
                elif parameters[0] == 'restart':
                    # restart + update
                    return
            elif parameters[0] == 'delete':
                # delete reminder
                return
            else:
                # assume its reminder otherwise
                asyncio.create_task(create_reminders(message))
                # async create task send confirmation
            return
    # if auther == bot and begins with confirmation message
    # attatch reactions
    return

async def create_reminders(message):
    global reminder_tasks, user_reminders
    # remove command_prefix from content and remove first space
    no_prefix = message.content[message.content.find(' ')+1:]

    # extract times from no_prefix
    extracted_times = search_dates(no_prefix, settings={'PREFER_DATES_FROM' : 'future', 'PREFER_DAY_OF_MONTH' : 'first', 'RELATIVE_BASE' : message.created_at})

    # if extracted_times == None -> error and return

    # add extracted time strings to delimiters list
    delimiters = []
    for i in range(len(extracted_times)):
        delimiters.append(extracted_times[i][0])

    # create regex pattern of time strings from delimiters list
    regex_pattern = '|'.join(map(re.escape, delimiters))

    # split message from the first space (to exclude the command_prefix) by regex pattern
    reminder_messages = re.split(regex_pattern, no_prefix)

    # strip each message of leading and trailing whitespace
    reminder_messages = [reminder_message.strip() for reminder_message in reminder_messages if reminder_message]

    for i in range(max(len(extracted_times),len(reminder_messages))):
        new_reminder = Reminder(message.author,message,message.channel,message.guild)
        if i in range(len(extracted_times)):
            new_reminder.time = extracted_times[i][1]
        if i in range(len(reminder_messages)):
            new_reminder.info = reminder_messages[i]
        user_reminders[message.author].append(new_reminder)
        # create task for sleeping and append to remind_tasks
        # asyncio.run_coroutine_threadsafe(run_reminder(new_reminder),asyncio.get_event_loop())
        asyncio.create_task(run_reminder(new_reminder))
    
    # debugging
    for key in user_reminders.keys():
        for i in range(len(user_reminders[key])):
            user_reminders[key][i].to_string()
            # await run_reminder(user_reminders[key][i])

async def run_reminder(reminder):
    delay = reminder.time - datetime.datetime.now()
    await asyncio.sleep(delay.total_seconds())
    await reminder.channel.send(reminder.info)
    # while datetime.datetime.now() < reminder.time:
    #     await asyncio.sleep(1)
    # delete from user_reminders and reminder_tasks
    # while True:
    #     if datetime.datetime.now() >= reminder.time:
    #         await reminder.channel.send(reminder.info)
    #         return
    #     else:
    #         await asyncio.sleep(1)
    print(reminder.info)
    return

# main function
def main():
    setup_tokens(tokensfile)
    # setup existing reminders, read from JSON
    # build_help_message()
    asyncio.get_event_loop().create_task(client.start(discord_token))
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.get_event_loop().run_until_complete(client.logout())
    finally:
        asyncio.get_event_loop().stop()

if __name__ == "__main__": main()
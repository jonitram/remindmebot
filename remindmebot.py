#!/usr/bin/env python3
import asyncio
import discord
from dateparser.search import search_dates
from dateparser import parse
import datetime
import re
import os
import pickle

# api tokens
discord_token=None

# DEAD LINK WILL NOT TAKE USER ANYWHERE, DO NOT NEED TO STORE JUMP URL ANYMORE

# the text file that the tokens are stored in
tokensfile = "tokens.txt"
# json file where 
reminders_file = "reminders.pkl"

# a list of message prefixes the bot will respond to
# index [0] is the default
command_prefixes = ['rm','remindme','remind','reminder','rm!','remindme!','!rm','!remindme']

commands = ['clear','delete','help','reminders','restart']
emojis = ['🇦','🇧','🇨','🇩','🇪']

help_messages = [' \"clear\" : Deletes commands issued to the bot and messages sent by the bot in the current channel (Up to 500 messages back).',
                 ' \"delete <Reminder>/all\" : Deletes the specified reminder / all of your reminders.'
                     '\nYou can specify a reminder using its reminder message or its number on the \"reminders\" list',
                 ' \"help\" : Sends the help message.',
                 ' \"reminders\" : Sends a list of your active reminders.',
                 ' \"restart\" : Restarts and updates the bot.']

confirmation_options = ['Delete this reminder (Will also delete both messages).',
                        'Delete both messages.',
                        'Delete this message.',
                        'Delete the message that created this reminder.']

reminder_tasks = {}
# Reminder -> background sleep task
user_reminders = {}
# user -> Reminders[]

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
    def __init__(self, user_id, message_id, channel_id, creation_time, jump_url, time=parse("in 1 day").strftime("%m/%d/%Y, %H:%M:%S"), info='', confirmation_id=None):
        self.user_id = user_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.creation_time = creation_time
        self.jump_url = jump_url
        self.time = time
        self.info = info
        self.confirmation_id = confirmation_id
    
    
    def pickle(self):
        with open(reminders_file, 'ab') as outfile:
            pickle.dump(self,outfile,pickle.HIGHEST_PROTOCOL)
        outfile.close()
        return
    
    # for use as a dictionary key
    def __hash__(self):
        return hash((self.message_id, self.time, self.info))
    
    def __eq__(self, other):
        if other == None:
            return False
        return (self.message_id, self.time, self.info) == (other.message_id, other.time, other.info)
    
    def __ne__(self, other):
        return not(self == other)

    # for debugging
    def to_string(self):
        print('User Name: {0} Message ID: {1} Channel ID: {2} Time: {3} Info: {4}'.format(self.user_id,self.message_id,self.channel_id,self.time,self.info))

@client.event
async def on_message(message):
    for prefix in command_prefixes:
        if message.content.lower().startswith(prefix + ' '):
            # remove prefix, whatever it was
            parameters = message.content.lower().replace(prefix,'',1).split()
            if len(parameters) == 1:
                if parameters[0] == 'help':
                    # done
                    help_message = build_help_message(message.author.mention)
                    await message.channel.send(help_message)
                    return
                elif parameters[0] == 'reminders':
                    await message.channel.send(print_reminders(message.author))
                    return
                elif parameters[0] == 'clear':
                    # clear
                    return
                elif parameters[0] == 'restart':
                    # restart + update
                    return
            elif parameters[0] == 'delete':
                if len(parameters) == 2 and parameters[1] == 'all':
                    if message.author in user_reminders:
                        if len(user_reminders[message.author]) > 0:
                            for reminder in user_reminders[message.author]:
                                asyncio.create_task(cancel_reminder(reminder))
                            return
                reminder = filter_reminders(message.author, message.content.lower().replace(prefix,'',1).replace('delete','',1).strip())
                if reminder != None:
                    await cancel_reminder(reminder)
                    return
            # fall through, assume its reminder otherwise
            await create_reminders(message)
            return
    if message.author.id == client.user.id:
        if message.content.endswith(build_reaction_options(confirmation_options)):
            for i in range(len(confirmation_options)):
                asyncio.create_task(message.add_reaction(emojis[i]))
        elif message.content.endswith(build_help_message('')):
            for i in range(len(commands)):
                asyncio.create_task(message.add_reaction(emojis[i]))
    return

async def cancel_reminder(reminder):
    global user_reminders, reminder_tasks
    user = client.get_user(reminder.user_id)
    user_reminders[user].remove(reminder)
    reminder_tasks[reminder].cancel()
    del reminder_tasks[reminder]
    channel = client.get_channel(reminder.channel_id)
    try:
        message = await channel.fetch_message(reminder.message_id)
    except discord.NotFound:
        pass
    else:
        await message.delete()
    try:
        confirmation = await channel.fetch_message(reminder.confirmation_id)
    except discord.NotFound:
        pass
    else:
        await confirmation.delete()
    result = user.mention + ' The reminder for \"{0}\" set to go off at {1} has been deleted.'.format(reminder.info,reminder.time)
    await channel.send(result)
    return

def filter_reminders(user, content):
    global user_reminders
    if user in user_reminders:
        for reminder in user_reminders[user]:
            if content == reminder.info:
                return reminder
        if content.isdigit():
            if int(content)-1 < len(user_reminders[user]):
                return user_reminders[user][int(content)-1]
    return None

def list_reminders(user):
    result = []
    print(user_reminders)
    if user in user_reminders:
        for reminder in user_reminders[user]:
            result.append(reminder)
    return result

def print_reminders(user):
    result = user.mention + ' Here is a list of your active reminders:'
    index = 1
    for reminder in list_reminders(user):
        # try fetch message if notfound -> don't link it
        # try channel.name if attributeerror -> don't link it
        result += '\n{0} - \"{1}\" for {2} in this channel \"{3}\". Here is a link to the original message: <{4}>'.format(index, reminder.info, reminder.time,  client.get_channel(reminder.channel_id).name, reminder.jump_url)
        index += 1
    if index == 1:
        result += '\nYou have no active reminders!'
    return result

@client.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name in emojis:
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.id == client.user.id and client.user.id != payload.user_id:
            option = emojis.index(payload.emoji.name)
            user = client.get_user(payload.user_id)
            # confirmation options
            if message.content.endswith(build_reaction_options(confirmation_options)):
                if message.content[:message.content.find(' ')].replace('!','') == user.mention:
                    # extract trigger message
                    if option == 0:
                        for reminder in user_reminders[user]:
                            try:
                                confirmation = await channel.fetch_message(reminder.confirmation_id)
                            except discord.NotFound:
                                continue
                            else:
                                if confirmation.content == message.content:
                                    await cancel_reminder(reminder)
                                    return
                    if option == 1:
                        # try delete trigger message
                        return
                    elif option == 2:
                        message.delete()
                    elif option == 3:
                        # try delete trigger message
                        try:
                            await message.delete()
                        except discord.NotFound:
                            pass
                        return
            elif message.content.endswith(build_help_message('')):
                help_message = user.mention + help_messages[emojis.index(payload.emoji.name)]
                await channel.send(help_message)
                return
    return


def build_help_message(mention):
    result = mention + ' Create a reminder by using any message prefix with a specified message and a specified time. A reminder can be created without a message and a reminder can be created without a specified time (defaults to 1 day).'
    result += '\nHere is a list of message prefixes the bot will respond to: '
    for i in range(len(command_prefixes)-1):
        result += '\"' + command_prefixes[i] + '\", '
    result += 'and \"' + command_prefixes[len(command_prefixes)-1] + '\".'
    result += '\nHere is a list of available commands. If you would like to learn more about a command, please react to this message with that command\'s corresponding reaction:'
    result += '\n' + build_reaction_options(commands)
    return result

def build_reaction_options(options):
    result = ''
    for i in range(len(options)):
        result += ' | ' + emojis[i] +' - ' + options[i]
    result += ' |'
    return result

async def create_reminders(message):
    global reminder_tasks, user_reminders
    # remove command_prefix from content and remove first space
    no_prefix = message.content[message.content.find(' ')+1:]
    
    # extract times from no_prefix
    extracted_times = search_dates(no_prefix, settings={'PREFER_DATES_FROM' : 'future', 'PREFER_DAY_OF_MONTH' : 'first'})

    if extracted_times != None:

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

    # edge case where only a message is input with no time
    else:
        # weird bug where if extracted_times == () -> wouldn't execute loop below
        extracted_times = ()
        reminder_messages = [no_prefix.strip()]

    for i in range(max(len(extracted_times),len(reminder_messages))):
        new_reminder = Reminder(message.author.id,message.id,message.channel.id,message.created_at.strftime("%H:%M:%S on %b %d, %Y"),message.jump_url)
        if i in range(len(extracted_times)):
            if extracted_times[i][1] < datetime.datetime.now():
                # error about making a reminder set to go off in the past
                # print date it would be created at in error
                return
            new_reminder.time = extracted_times[i][1].strftime("%H:%M:%S on %b %d, %Y")
        if i in range(len(reminder_messages)):
            new_reminder.info = reminder_messages[i]
        if message.author not in user_reminders:
            user_reminders[message.author] = []
        confirmation_message = '{0} A reminder has been created for \"{1}\" and has been set to go off at {2}.\nReact to this message with these reactions to perform these commands:\n{3}'.format(message.author.mention, new_reminder.info, new_reminder.time, build_reaction_options(confirmation_options))
        confirmation = await message.channel.send(confirmation_message)
        new_reminder.confirmation_id = confirmation.id
        user_reminders[message.author].append(new_reminder)
        # create task for sleeping and append to remind_tasks
        reminder_tasks[new_reminder] = asyncio.create_task(run_reminder(new_reminder))
    
    # debugging
    # for key in user_reminders.keys():
    #     for i in range(len(user_reminders[key])):
    #         user_reminders[key][i].to_string()

    return

async def run_reminder(reminder):
    # set delay once but run into the problem of negative numbers for the past
    # delay = reminder.time - datetime.datetime.now()
    # await asyncio.sleep(delay.total_seconds())
    # await reminder.channel.send(reminder.info)
    user = client.get_user(reminder.user_id)
    result = '{0} Reminder for \"{1}\" from {2}.\nHere is a link to the original message: {3}'.format(user.mention, reminder.info, reminder.creation_time,reminder.jump_url) 
    
    expiration = parse(reminder.time)
    # check constantly with micro sleeps
    while datetime.datetime.now() < expiration:
        await asyncio.sleep(0.1)
    
    # send reminder
    await reminder.channel.send(result)

    # clear global lists
    user_reminders[reminder.user].remove(reminder)
    del reminder_tasks[reminder]
    return

def save_reminders():
    for reminder in reminder_tasks.keys():
        reminder.pickle()
    return

async def load_reminders():
    global user_reminders, reminder_tasks
    reminders = []
    if reminders_file in os.listdir(os.getcwd()):
        with open(reminders_file, 'rb') as infile:
            while True:
                try:
                    reminders.append(pickle.load(infile))
                except EOFError:
                    break
        os.remove(reminders_file)
    for reminder in reminders:
        user = client.get_user(reminder.user_id)
        if user not in user_reminders:
            user_reminders[user] = []
        user_reminders[user].append(reminder)
        reminder_tasks[reminder] = asyncio.create_task(run_reminder(reminder))
    return

@client.event
async def on_ready():
    await load_reminders()
    return

# main function
def main():
    setup_tokens(tokensfile)
    # setup existing reminders, read from JSON
    # client.run(discord_token)
    try:
        asyncio.get_event_loop().run_until_complete(client.start(discord_token))
    except KeyboardInterrupt:
        # need to change keyboard interrupt to write out existing reminders to json before exiting
        save_reminders()
        asyncio.get_event_loop().run_until_complete(client.logout())
    finally:
        asyncio.get_event_loop().close()

if __name__ == "__main__": main()
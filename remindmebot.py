#!/usr/bin/env python3
import asyncio
from dateparser import parse
from dateparser.search import search_dates
from datetime import datetime, timezone
import discord
import os
import pickle
import re

### TODO ###
# need to add catching exceptions for DM reminders
# ^ that won't stop the bot, but will cause terminal to output tons of random garbage

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
                        'Delete this message.',
                        'Delete the message that created this reminder.',
                        'Delete both messages.']

# Reminder -> asyncio task running the reminder
reminder_tasks = {}
# user -> Reminder[]
user_reminders = {}

### REMINDER CLASS ####

class Reminder:
    def __init__(self, user_id, message_id, channel_id, creation_time, reminder_time=parse("in 1 day").strftime("%H:%M:%S on %b %d, %Y"), info='', confirmation_id=None):
        self.user_id = user_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.creation_time = creation_time
        self.reminder_time = reminder_time
        self.info = info
        self.confirmation_id = confirmation_id
    
    def save_reminder(self, file_name):
        with open(file_name, 'ab') as outfile:
            pickle.dump(self,outfile, pickle.HIGHEST_PROTOCOL)
        outfile.close()
        return
    
    # for use as a dictionary key
    def __hash__(self):
        return hash((self.message_id, self.reminder_time, self.info))
    
    def __eq__(self, other):
        if other == None:
            return False
        return (self.message_id, self.reminder_time, self.info) == (other.message_id, other.reminder_time, other.info)
    
    def __ne__(self, other):
        return not(self == other)

    # for debugging
    def to_string(self):
        print('User ID: {0} Message ID: {1} Channel ID: {2} Time: {3} Info: {4}'.format(self.user_id, self.message_id, self.channel_id, self.reminder_time, self.info))

### BUILDING MESSAGES ###

def build_help_message(mention):
    result = mention + ' Create a reminder by using any message prefix with a specific reminder message and a specific time.'
    result += 'A reminder can be created without a message and a reminder can be created without a time (defaults to in 1 day).'
    result += '\nEx: \"remindme test in 2 hours\" will create a reminder in 2 hours with the reminder message \"test\".'
    result += '\nHere is a list of message prefixes the bot will respond: '
    for i in range(len(bot_prefixes)-1):
        result += '\"' + bot_prefixes[i] + '\", '
    result += 'and \"' + bot_prefixes[len(bot_prefixes)-1] + '\".'
    result += '\nAs long as the first word in your message begins with a prefix, the bot will respond.'
    result += '\nHere is a list of available commands. If you would like to learn more about a command, please react to this message with that command\'s corresponding reaction:'
    result += '\n' + build_reaction_options(commands)
    return result

def build_reaction_options(options):
    result = ''
    for i in range(len(options)):
        result += '| ' + emojis[i] +' - ' + options[i] + ' '
    result += '|'
    return result

async def build_reminders(user):
    result = user.mention + ' Here is a list of your active reminders:'
    index = 0
    if user in user_reminders:
        if len(user_reminders[user]) > 0:
            for reminder in user_reminders[user]:
                index += 1
                result += '\n{0} - \"{1}\" for {2} in this channel: '.format(index, reminder.info, reminder.reminder_time)
                try:
                    channel_name = client.get_channel(reminder.channel_id).name
                except AttributeError:
                    result += 'Bot DMs. '
                else:
                    result += '\"{0}\". '.format(channel_name)
                try:
                    message = await client.get_channel(reminder.channel_id).fetch_message(reminder.message_id)
                except discord.NotFound:
                    pass
                else:
                    result += 'Here is a link to the original message: {0}'.format(message.jump_url)
    if index == 0:
        result += '\nYou have no active reminders!'
    return result

### I/O ###

def setup_tokens(file_name):
    global discord_token
    tokens = open(file_name, "r")
    discord_token = tokens.readline().rstrip()
    tokens.close()
    return

def save_reminders(output_file):
    for reminder in reminder_tasks.keys():
        reminder.save_reminder(output_file)
    return

async def load_reminders(input_file):
    global user_reminders, reminder_tasks
    reminders = []
    if input_file in os.listdir(os.getcwd()):
        with open(input_file, 'rb') as infile:
            while True:
                try:
                    reminders.append(pickle.load(infile))
                except EOFError:
                    break
        infile.close()
        os.remove(input_file)
    for reminder in reminders:
        user = client.get_user(reminder.user_id)
        if user not in user_reminders:
            user_reminders[user] = []
        user_reminders[user].append(reminder)
        reminder_tasks[reminder] = asyncio.create_task(run_reminder(reminder))
    return

### DISCORD ###

# the discord client
help_activity = discord.Activity(name='\"' + bot_prefixes[0] + ' help\" for help',type=discord.ActivityType.playing)
client = discord.Client(activity=help_activity)

@client.event
async def on_ready():
    print('Loading in saved reminders:')
    await load_reminders(save_file)
    print('Done. The bot is ready to go!')
    return

@client.event
async def on_message(message):
    for prefix in bot_prefixes:
        if message.content.lower().startswith(prefix):
            _, _, removed_prefix = message.content.lower().partition(' ')
            parameters = removed_prefix.split()
            if len(parameters) > 0:
                if len(parameters) == 1:
                    if parameters[0] == 'help':
                        await message.channel.send(build_help_message(message.author.mention))
                        return
                    elif parameters[0] == 'reminders':
                        await message.channel.send(await build_reminders(message.author))
                        return
                    elif parameters[0] == 'clear':
                        asyncio.create_task(clear_messages(message))
                        return
                    elif parameters[0] == 'restart':
                        await restart(message)
                        return
                elif parameters[0] == 'delete':
                    if message.author in user_reminders:
                        if len(parameters) == 2 and parameters[1] == 'all':
                            if len(user_reminders[message.author]) > 0:
                                for reminder in user_reminders[message.author]:
                                    asyncio.create_task(cancel_reminder(reminder))
                                return
                        else:
                            reminder = get_reminder(message.author, removed_prefix.replace('delete','',1).strip())
                            if reminder != None:
                                asyncio.create_task(cancel_reminder(reminder))
                                return
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

@client.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name in emojis:
        channel = client.get_channel(payload.channel_id)
        this_message = await channel.fetch_message(payload.message_id)
        if this_message.author.id == client.user.id and client.user.id != payload.user_id:
            option = emojis.index(payload.emoji.name)
            user = client.get_user(payload.user_id)
            # confirmation options
            if this_message.content.endswith(build_reaction_options(confirmation_options)):
                if this_message.content[:this_message.content.find(' ')].replace('!','') == user.mention:
                    for reminder in user_reminders[user]:
                        try:
                            confirmation = await channel.fetch_message(reminder.confirmation_id)
                        except discord.NotFound:
                            continue
                        else:
                            if confirmation.content == this_message.content:
                                if option == 0:
                                    await cancel_reminder(reminder)
                                    return
                                if option == 1 or option == 3:
                                    await this_message.delete()
                                if option == 2 or option == 3:
                                    try:
                                        trigger_message = await channel.fetch_message(reminder.message_id)
                                    except discord.NotFound:
                                        pass
                                    else:
                                        await trigger_message.delete()
                            return
            # help message
            elif this_message.content.endswith(build_help_message('')):
                await channel.send(user.mention + help_messages[emojis.index(payload.emoji.name)])
                return
    return

async def clear_messages(message):
    deleted = asyncio.create_task(message.channel.purge(limit=500, check=clear_conditions))
    while True:
        try:
            deleted.result()
        except asyncio.base_futures.InvalidStateError:
            await asyncio.sleep(0.1)
        else:
            break

def clear_conditions(message):
    if message.author.id == client.user.id:
        return True
    for prefix in bot_prefixes:
        if message.content.startswith(prefix):
            return True
    return False

async def restart(message):
    save_reminders(save_file)
    await message.channel.send(message.author.mention + ' Restarting the bot!')
    os.system('sh restart.sh')
    return

### REMINDER INTERACTION ###

async def create_reminders(message):
    global reminder_tasks, user_reminders
    # remove prefix from content and remove first space
    _, _, removed_prefix = message.content.partition(' ')
    removed_prefix.strip()
    # extract times from removed_prefix
    extracted_times = search_dates(removed_prefix, settings={'PREFER_DATES_FROM' : 'future', 'PREFER_DAY_OF_MONTH' : 'first'})
    if extracted_times != None:
        # add extracted time strings to delimiters list
        delimiters = []
        for i in range(len(extracted_times)):
            delimiters.append(extracted_times[i][0])
        # create regex pattern of time strings from delimiters list
        regex_pattern = '|'.join(map(re.escape, delimiters))
        # split message from the first space (to exclude the prefix) by regex pattern
        reminder_messages = re.split(regex_pattern, removed_prefix)
        # strip each message of leading and trailing whitespace
        reminder_messages = [reminder_message.strip() for reminder_message in reminder_messages if reminder_message]
    # edge case where only a message is input with no time
    else:
        # weird bug where if extracted_times == () -> wouldn't execute loop below
        extracted_times = ()
        reminder_messages = [removed_prefix]
    
    for i in range(max(len(extracted_times),len(reminder_messages))):
        new_reminder = Reminder(message.author.id,message.id,message.channel.id,message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%H:%M:%S on %b %d, %Y"))
        if i in range(len(extracted_times)):
            new_reminder.reminder_time = extracted_times[i][1].strftime("%H:%M:%S on %b %d, %Y")
        if i in range(len(reminder_messages)):
            new_reminder.info = reminder_messages[i]
        if parse(new_reminder.reminder_time) < datetime.datetime.now():
            error_message = message.author.mention + ' You cannot create a reminder set to go off in the past. The reminder \"{0}\" set to go off at {1} was not created.'.format(new_reminder.info, new_reminder.reminder_time)
            await message.channel.send(error_message)
            return
        if message.author not in user_reminders:
            user_reminders[message.author] = []
        confirmation_message = '{0} A reminder has been created for \"{1}\" and has been set to go off at {2}.\nReact to this message with these reactions to perform these commands:\n{3}'.format(message.author.mention, new_reminder.info, new_reminder.reminder_time, build_reaction_options(confirmation_options))
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
    global user_reminders, reminder_tasks
    user = client.get_user(reminder.user_id)
    result = '{0} Reminder for \"{1}\" from {2}.'.format(user.mention, reminder.info, reminder.creation_time) 
    expiration = parse(reminder.reminder_time)
    # check constantly with micro sleeps
    while datetime.datetime.now() < expiration:
        await asyncio.sleep(0.1)
    try:
        message = await client.get_channel(reminder.channel_id).fetch_message(reminder.message_id)
    except discord.NotFound:
        pass
    else:
        result += ' Here is a link to the original message: {0}'.format(message.jump_url)
    # send reminder
    await client.get_channel(reminder.channel_id).send(result)
    # clear global lists
    user_reminders[user].remove(reminder)
    del reminder_tasks[reminder]
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
    result = user.mention + ' The reminder for \"{0}\" set to go off at {1} has been deleted.'.format(reminder.info,reminder.reminder_time)
    await channel.send(result)
    return

def get_reminder(user, content):
    global user_reminders
    if user in user_reminders:
        for reminder in user_reminders[user]:
            if content == reminder.info:
                return reminder
        if content.isdigit():
            if int(content)-1 < len(user_reminders[user]):
                return user_reminders[user][int(content)-1]
    return None

### MAIN ###

def main():
    setup_tokens(tokens_file)
    # setup existing reminders, read from save_file
    try:
        asyncio.get_event_loop().run_until_complete(client.start(discord_token))
    except KeyboardInterrupt:
        save_reminders(save_file)
        asyncio.get_event_loop().run_until_complete(client.logout())
    finally:
        asyncio.get_event_loop().close()

if __name__ == "__main__": main()
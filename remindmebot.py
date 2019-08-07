#!/usr/bin/env python3
import asyncio
import discord
from dateparser.search import search_dates
from dateparser import parse
import datetime
import re

# api tokens
discord_token=None

# the text file that the tokens are stored in
tokensfile = "tokens.txt"

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

confirmation_options = ['Delete this reminder.',
                        'Delete the message that created this reminder.',
                        'Delete this message.',
                        'Delete both messages.']

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
    def __init__(self, user, message, channel, time=parse("in 1 day"), info='', confirmation=None):
        self.user = user
        self.message = message
        self.channel = channel
        self.time = time
        self.info = info
        self.confirmation = confirmation
    
    # for use as a dictionary key
    def __hash__(self):
        return hash((self.message, self.time, self.info))
    
    def __eq__(self, other):
        return (self.message, self.time, self.info) == (self.message, self.time, self.info)
    
    def __ne__(self, other):
        return not(self == other)

    # for debugging
    def to_string(self):
        print('User Name: {0} Message ID: {1} Channel ID: {2} Time: {3} Info: {4} Confirmation Content: {5}'.format(self.user.name,self.message.id,self.channel.id,self.time.strftime("%m/%d/%Y, %H:%M:%S"),self.info, self.confirmation.content))

@client.event
async def on_message(message):
    for prefix in command_prefixes:
        if message.content.lower().startswith(prefix + ' '):
            parameters = message.content.lower().replace(prefix,'',1).split()
            if len(parameters) == 1:
                if parameters[0] == 'help':
                    help_message = message.author.mention + build_help_message()
                    asyncio.create_task(message.channel.send(help_message))
                    return
                elif parameters[0] == 'reminders':
                    asyncio.create_task(message.channel.send(list_reminders(message.author)))
                    return
                elif parameters[0] == 'clear':
                    # clear
                    return
                elif parameters[0] == 'restart':
                    # restart + update
                    return
                else:
                    # one word reminder
                    asyncio.create_task(create_reminders(message))
            elif parameters[0] == 'delete':
                if len(parameters) == 2 and parameters[1] == 'all':
                    # loop through all users reminders
                    return
                reminder = filter_reminders(message.author, prefix, message.content)
                if reminder != None:
                    asyncio.create_task(delete_reminder(reminder))
                else:
                    asyncio.create_task(create_reminders(message))
                return
            else:
                # assume its reminder otherwise
                asyncio.create_task(create_reminders(message))
            return
    if message.author.id == client.user.id:
        if message.content.endswith(build_reaction_options(confirmation_options)):
            for i in range(len(confirmation_options)):
                asyncio.create_task(message.add_reaction(emojis[i]))
        elif message.content.endswith(build_help_message()):
            for i in range(len(commands)):
                asyncio.create_task(message.add_reaction(emojis[i]))
    return

def filter_reminders(user, prefix, message_content):
    trimmed_content = message_content.replace('delete','')[message_content.index(' '):].strip()
    if user in user_reminders:
        if trimmed_content.isdigit():
            if int(trimmed_content)-1 < len(user_reminders[user]):
                return user_reminders[user][int(trimmed_content)-1]
        for reminder in user_reminders[user]:
            if trimmed_content == reminder.info:
                return reminder
    return None

#make this compatible using invalid state erorr like clear from sbb
async def delete_reminder(reminder):
    global user_reminders, reminder_tasks
    if reminder in user_reminders[reminder.user]:
        user_reminders[reminder.user].remove(reminder)
    
    if reminder in reminder_tasks:
        try:
            reminder_tasks[reminder].result()
        except asyncio.base_futures.InvalidStateError:
            reminder_tasks[reminder].cancel()
            try:
                await reminder.message.delete()
            except discord.NotFound:
                pass
            formatted_time = reminder.time.strftime("%H:%M:%S on %b %d, %Y")
            result = reminder.user.mention + ' The reminder for \"{0}\" set to go off at {1} has been deleted.'.format(reminder.info,formatted_time)
        else:
            original_timestamp = reminder.message.created_at.strftime("%H:%M:%S on %b %d, %Y")
            result = '{0} Reminder for \"{1}\" from {2}.\nHere is a link to the original message: {3}'.format(reminder.user.mention, reminder.info, original_timestamp,reminder.message.jump_url) 
        del reminder_tasks[reminder]
    try:
        await reminder.confirmation.delete()
    except discord.NotFound:
        pass
    asyncio.create_task(reminder.channel.send(result))
    return

def list_reminders(user):
    result = None
    if user in user_reminders:
        if len(user_reminders[user]) > 0:
            result = user.mention + ' Here is a list of your active reminders:'
            for i in range(len(user_reminders[user])):
                formatted_time = user_reminders[user][i].time.strftime("%H:%M:%S on %b %d, %Y")
                result += '\n{0} - \"{1}\" for {2}'.format(1+i,user_reminders[user][i].info,formatted_time)
    if result == None:
        result = user.mention + ' You currently have no reminders set!'
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
                if user in user_reminders:
                    # SITUATION WHERE REMINDER HAS COMPLETED BUT USER STILL INTERACTS WITH MESSAGES
                    # SHOULD VALIDATE ID BASED ON MENTION AT THE BEGINNING OF MESSAGE THROUGH THE FIRST SPACE
                    for i in range(len(user_reminders[user])):
                        if user_reminders[user][i].confirmation.id == message.id:
                            if option == 0:
                                asyncio.create_task(delete_reminder(user_reminders[user][i]))
                                return
                            elif option == 1:
                                try:
                                    await user_reminders[user][i].message.delete()
                                except discord.NotFound:
                                    pass
                                return
                            elif option == 2:
                                try:
                                    await user_reminders[user][i].confirmation.delete()
                                except discord.NotFound:
                                    pass
                                return
                            elif option == 3:
                                try:
                                    await user_reminders[user][i].message.delete()
                                except discord.NotFound:
                                    pass
                                try:
                                    await user_reminders[user][i].confirmation.delete()
                                except discord.NotFound:
                                    pass
                                return
            elif message.content.endswith(build_help_message()):
                help_message = user.mention + help_messages[emojis.index(payload.emoji.name)]
                asyncio.create_task(channel.send(help_message))
                return
    return


def build_help_message():
    result = ' Create a reminder by using any message prefix with a specified message and a specified time. A reminder can be created without a message and a reminder can be created without a specified time (defaults to 1 day).'
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
        new_reminder = Reminder(message.author,message,message.channel)
        if i in range(len(extracted_times)):
            new_reminder.time = extracted_times[i][1]
        if i in range(len(reminder_messages)):
            new_reminder.info = reminder_messages[i]
        if message.author not in user_reminders:
            user_reminders[message.author] = []
        user_reminders[message.author].append(new_reminder)
        # create task for sleeping and append to remind_tasks
        reminder_tasks[new_reminder] = asyncio.create_task(run_reminder(new_reminder))
        formatted_time = new_reminder.time.strftime("%H:%M:%S on %b %d, %Y")
        confirmation_message = '{0} A reminder has been created for \"{1}\" and has been set to go off at {2}.\nReact to this message with these reactions to perform these commands:\n{3}'.format(new_reminder.user.mention, new_reminder.info, formatted_time, build_reaction_options(confirmation_options))
        new_reminder.confirmation = await new_reminder.channel.send(confirmation_message)
    
    # debugging
    for key in user_reminders.keys():
        for i in range(len(user_reminders[key])):
            user_reminders[key][i].to_string()

async def run_reminder(reminder):
    global user_reminders, reminder_tasks

    # set delay once but run into the problem of negative numbers for the past
    # delay = reminder.time - datetime.datetime.now()
    # await asyncio.sleep(delay.total_seconds())
    # await reminder.channel.send(reminder.info)

    #check constantly with micro sleeps
    while datetime.datetime.now() < reminder.time:
        await asyncio.sleep(0.1)
    await delete_reminder(reminder)
    return

# main function
def main():
    setup_tokens(tokensfile)
    # setup existing reminders, read from JSON
    # build_help_message()
    client.run(discord_token)
    # asyncio.get_event_loop().create_task(client.start(discord_token))
    # try:
    #     asyncio.get_event_loop().run_forever()
    # except KeyboardInterrupt:
    #     need to change keyboard interrupt to write out existing reminders to json before exiting
    #     asyncio.get_event_loop().run_until_complete(client.logout())
    # finally:
    #     asyncio.get_event_loop().stop()

if __name__ == "__main__": main()
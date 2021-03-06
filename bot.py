# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
from report import Report
from database import Database
from unidecode import unidecode 

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None   
        self.group_channel = None # Main group channel
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.reported = {} # Map from message IDs to boolean to forward
        self.perspective_key = key
        self.db = Database()

    async def on_ready(self):

        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")
        
        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}':
                    self.group_channel = channel
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_raw_reaction_add(self, payload):
        '''
        This function is called whenever a user reacts to a message in a channel that the bot can see.
        Currently the bot is configured to send a message describing the action taken to the "group-#-mod" channel.
        '''
        if payload.guild_id not in self.mod_channels:
            return
        if payload.channel_id != self.mod_channels[payload.guild_id].id:
            return
        mod_channel = self.mod_channels[payload.guild_id]
        message = await mod_channel.fetch_message(payload.message_id)
        
        # Make sure it's a report forwarded by the bot
        if message.reference is not None or message.author.id != self.user.id:
            return

        # Get message ID from forwarded report content
        original_message_ID = int(message.content.split(' ')[4])
        original_message = None
        try:
            original_message = await self.group_channel.fetch_message(original_message_ID)
        except:
            return

        if payload.emoji.name == '????':
            r = (f"Sufficient public indication that Tweet is a scam according to {payload.member.name}. "
            "Applying warning to Tweet. "
            "Please reply to this message with a content reviewer report. "
            )
            prompt = await message.reply(r)
            # Marks as requiring content review report
            self.db.add_prompt(prompt.id, original_message_ID)
            await original_message.reply('Warning: Tweet has been confirmed to be a scam by the content moderation team.')
        elif payload.emoji.name == '????':
            r = (f"Insufficient public indication that Tweet is a scam according to {payload.member.name}. "
            "Applying warning to Tweet. "
            )
            await message.reply(r)
            self.db.add_not_severe(original_message_ID)
            await original_message.reply('Warning: Tweet has been reported by users as a scam.')
        elif payload.emoji.name == '???':
            await original_message.delete()
            r = (f"Previous content reviewer reports suggest Tweet should be deleted according to {payload.member.name}. "
            "Deleting Tweet."
            )
            await message.reply(r)
    
    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from us 
        if message.author.id == self.user.id:
            return
        
        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)
    
    async def on_message_edit(self, before, after):
        """
        This function is called whenever a message is edited.
        The bot is configured to check if a cryptoaddress has been edited, and whether or not the new message contains a
        blacklisted crypto address.
        """
        with open("blacklist.txt", "r") as file:
            addresses = file.readlines()
            for add in addresses:
                add = add.strip()
                if add in after.content:
                    r = "Message has been edited to contain fraudulent or suspicious crypto addresses. "
                    await after.reply(r)
                    break
                elif add in before.content:
                    r = "Message previously containing fraudulent/suspicious crypto addresses have been edited to contain a new crypto address."
                    await after.reply(r)
                    break
            file.close()
    
    async def fwd_reported(self, message_id):
        message = await self.group_channel.fetch_message(message_id)
        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]

        fwd = f'Forwarded message with ID {message.id} \n{message.author.name}: "{message.content}"'

        fwd += '\n\nPrevious content reviewer reports include the following: '
        message_info = self.db.get_cr_reports(message.id)
        if message_info == None:
            fwd += '\nNo reports found.'
        else:
            for i in range(1, message_info['cr_report_count'] + 1):
                report = message_info['cr_reports'][i]
                author = report['author']
                desc = report['description']
                time = report['time']
                fwd += f'\nBy {author} at {time}: "{desc}"'
        fwd += '\n\nPlease review public engagement with Tweet and react to this message with ???? if it suggests the Tweet is a scam.'
        fwd += ' In this case, you will be asked to submit a content reviewer report.'
        fwd += ' Otherwise, react with ????.'
        fwd += ' If prior reviews indicate the original message should be deleted, react with ???.'
        await mod_channel.send(fwd)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            print("Send reply to help")
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)
        
        # Let the report class handle this message; forward all the messages it returns to us
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            # Get message ID corresponding to report
            mid = self.reports[author_id].message_id
            # Message ID identified (report completed)
            if mid > 0:
                # Check if message should be forwarded
                if self.reports[author_id].should_fwd or self.db.get_not_severe(mid) > 2:
                    await self.fwd_reported(mid)
                else:
                    self.db.add_not_severe(mid)
            # Remove complete/conacelled report from our map
            self.reports.pop(author_id)

    async def handle_mod_message(self, message):
        # Handle replies to reports in "group-#-mod" channel
        if message.channel.name == f'group-{self.group_num}-mod':
            # Message is a reply and message is not from bot
            if message.reference is not None and message.author.id != self.user.id:
                # Get prompt message
                ref_id = message.reference.message_id
                original_id = self.db.get_message_from_prompt(ref_id)
                # Message requires content reviewer report
                if original_id != None:
                    # Add report to database
                    time = message.created_at.strftime("%m/%d/%Y, %H:%M:%S")
                    report = self.create_report(message.author.name, time, message.content)
                    self.db.add_report(original_id, report)
                    self.db.remove_prompt(ref_id)
                    await message.reply(f'Successfully added content reviewer report for report message with ID {original_id}.')

    async def handle_channel_message(self, message):

        if message.channel.name == f'group-{self.group_num}-mod':
            await self.handle_mod_message(message)
            return

        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return 

        # Automated flagging using blacklist
        if (self.check_blacklist(message)):
            await message.reply("Message contains fraudulent or suspicious crypto address.")
            return
        
        # Automated flagging using classifier
        if (self.check_classifier(message)):
            self.db.add_not_severe(message.id)
            return

    def create_report(self, author, time, description):
        '''
        Given information about a report, create a dictionary representation of the report.
        '''
        report_dict = {
            'author': author,
            'time': time,
            'description': description
        }
        return report_dict

    def check_blacklist(self, message):
        with open("blacklist.txt", "r") as file:
            addresses = file.readlines()
            for add in addresses:
                add = add.strip()
                if add in message.content:
                    return True
        return False
    
    def check_classifier(self, message):

        # Check if messages are disguised in unicode
        content_decoded = unidecode(message.content, errors='preserve')
        if content_decoded != message.content:
            message.content = content_decoded

        string = message.content
        contains_btc_add = bool(re.search("[13][a-km-zA-HJ-NP-Z1-9]{25,34}", string))
        contains_eth_add = bool(re.search("0x[a-fA-F0-9]{40}$", string))
        phrases = ['legit', 'legitimate', 'send me', 'double', 'whatsapp']
        legit_bot_phrases = ['transferred from', 'move from']
        contains_scam_phrase = False
        for phrase in phrases:
            if phrase in string.lower():
                contains_scam_phrase = True
        contains_legit_phrase = False
        for phrase in legit_bot_phrases:
            if phrase in string.lower():
                contains_legit_phrase = True
        return ((not contains_legit_phrase) and (contains_btc_add or contains_eth_add or contains_scam_phrase))
            
        
client = ModBot(perspective_key)
client.run(discord_token)
# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
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
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.perspective_key = key

        self.to_cr_report = set() # Set of message IDs that require a content reviewer report

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

        if payload.emoji.name == '👍':
            r = (f"Sufficient public indication that Tweet is a scam according to {payload.member.name}. "
            "Applying warning to Tweet. "
            "Please reply to this message with content reviewer report. "
            )
            await message.reply(r)
            # Marks are requiring content review report
            self.to_cr_report.add(payload.message_id)
        elif payload.emoji.name == '👎':
            r = (f"Insufficient public indication that Tweet is a scam according to {payload.member.name}. "
            "Applying warning to Tweet, as well as additional information. "
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

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []
        print("line 82")

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            print("line 85")
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)
        
        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):

        # Handle replies to reports in "group-#-mod" channel
        if message.channel.name == f'group-{self.group_num}-mod':
            # Message is a reply and message is not from bot
            if message.reference is not None and message.author.id != self.user.id:
                ref_id = message.reference.message_id
                # Message requires content reviewer report
                if ref_id in self.to_cr_report:
                    # TODO: add report to backend storage
                    await message.reply(f'Successfully added content reviewer report for message with id {ref_id}.')
                    self.to_cr_report.remove(message.reference.message_id)

        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return 
        
        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]
        await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')

        scores = self.eval_text(message)
        await mod_channel.send(self.code_format(json.dumps(scores, indent=2)))

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'
        message.content = unidecode(message.content, errors='preserve')
        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message.content},
            'languages': ['en'],
            'requestedAttributes': {
                                    'SEVERE_TOXICITY': {}, 'PROFANITY': {},
                                    'IDENTITY_ATTACK': {}, 'THREAT': {},
                                    'TOXICITY': {}, 'FLIRTATION': {}
                                },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()
        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]

        return scores
    
    def code_format(self, text):
        return "```" + text + "```"
            
        
client = ModBot(perspective_key)
client.run(discord_token)
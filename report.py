from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    SCAM_IDENTIFIED = auto()
    REPORT_TYPPE_IDENTIFIED = auto()
    ABUSE_TYPE_IDENTIFIED = auto()
    ABUSE_DETAILS= auto()
    REPORT_COMPLETE = auto()
    SCAM_FOUND = auto()
    MISLEADING_TYPE = auto()
    NOT_RELATED_TO_FINANCE = auto()
    MONEY_CHECKED = auto()
    REPORT_ELSE = auto()
    ADDITIONAL_INFO = auto()
    MISLEADING_REASON = auto()
    CHECK_TYPE = auto()
    CHECK_MONEY = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Help us understand the problem. What's going on with this message? Please type the number of the following reaons: 1. I am not interested in this message. 2. It's suspicious or scam. 3. It's abusive or harmful. 4. It's misleading. 5. It expresses intentions of self-hard or suicide."]
      
        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content == "1": 
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]
            elif message.content == "2": 
                self.state = State.SCAM_FOUND
                return ["Is this message related to finance (investment, buying crytocurrencies etc.) Please answer yes or no."]

            elif message.content == "3": 
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]

            elif message.content == "4": 
                self.state = State.MISLEADING_TYPE
                
            elif message.content == "5": 
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]
            else: 
                return["Please choose a number."]
        if self.state == State.MISLEADING_TYPE: 
            self.state = State.MISLEADING_REASON
            return ["Why is this message misleading? Please type the number the of following reasons: 1. Politices 2. Health 3. Something else"]

        if self.state == State.MISLEADING_REASON: 
            if message.content == "1":
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]  
            elif message.content == "2":
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]
            elif message.content == "3":
                self.state = State.CHECK_TYPE
                return ["Is this message related to finance (investment, buying crytocurrencies etc.) Please answer yes or no."]
            else: 
                return ["Please choose a number."]

        if self.state == State.CHECK_TYPE:
            if message.content == "yes": 
                self.state = State.SCAM_IDENTIFIED
                return ["What's wrong with this message or the user who posted it? Please type the number the of following reasons: 1. Tweet is sending people to misleading url. 2. Account is impersonating someone else. 3. Something else"]
            elif message.content == "no":
                self.state = State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]
            else: 
                return["Please answer yes or no."]

        if self.state == State.SCAM_FOUND:
            if message.content == "yes": 
                self.state = State.SCAM_IDENTIFIED
                return ["What's wrong with this message or the user who posted it? Please type the number the of following reasons: 1. Tweet is sending people to misleading url. 2. Account is impersonating someone else. 3. Something else"]
            elif message.content == "no":
                self.state = State.NOT_RELATED_TO_FINANCE
                return ["What is the tweet related to?  Please type the number the of following reasons: 1. The accout posted the message is feak. 2. the message contains links to potentially harmful, malicious, phishing site. 3. The hashtags seem unrelated. 4. The message is a spam. 5. Someting else"]
            else: 
                return["Please answer yes or no."]
                
        if self.state == State.NOT_RELATED_TO_FINANCE: 
            if message.content == "1" or message.content == "2" or message.content == "3" or message.content == "4" or message.content == "5": 
                self.state= State.REPORT_COMPLETE
                return ["We will investigate this message and get back to you soon."]
            else: 
                return["Please choose a number."]

        if self.state == State.SCAM_IDENTIFIED:
            if message.content == "1":
                self.state = State.CHECK_MONEY 
                return ["Have you lost money due to interaction with this account? Please answer yes or no."]
            elif message.content == "2":
                self.state = State.CHECK_MONEY 
                return ["Have you lost money due to interaction with this account? Please answer yes or no."]
            elif message.content == "3":
                self.state = State.CHECK_MONEY 
                return ["Have you lost money due to interaction with this account? Please answer yes or no."]    
            else: 
                return["Please choose a number."]

        if self.state == State.CHECK_MONEY:
            if message.content == "yes":
                self.state = State.MONEY_CHECKED
            elif message.content == "no":
                self.state = State.MONEY_CHECKED        
            else: 
                return["Please answer yes or no."]

        if self.state == State.MONEY_CHECKED: 
            self.state = State.REPORT_ELSE
            return ["Anything else you would like to report? Please answer yes or no"]

        if self.state == State.REPORT_ELSE:
            if message.content == "yes":
                self.state = State.ADDITIONAL_INFO
                return ["Please type any information you think is relevant."]
            elif message.content == "no":
                self.state = State.REPORT_COMPLETE     
                return ["We will investigate this message and get back to you soon."]  
            else: 
                return["Please answer yes or no."]

        if self.state == State.ADDITIONAL_INFO:
            self.state = State.REPORT_COMPLETE     
            return ["We will investigate this message and get back to you soon."]  

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    


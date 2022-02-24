import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

class Database:

    def __init__(self):
        cred = credentials.Certificate('firebase-sdk.json')
        firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://cs-152-group-23-default-rtdb.firebaseio.com/'
        })

    def create_message_record(self, message_id):
        '''
        Given a message ID, create a new record for its reports in the database.
        '''
        ref = db.reference('/')
        ref.update({
            f'Messages/{message_id}': {
                'cr_reports': {},
                'cr_report_count': 0,
                'non_severe_count': 0
            },
        })
    
    def add_report(self, message_id, report):
        '''
        Given a content reviewer report containing author, time, and description, adds the report to the database.
        '''
        num_cr_reports = db.reference(f'Messages/{message_id}/cr_report_count').get()
        if num_cr_reports is None:
            self.create_message_record(message_id)
            num_cr_reports = db.reference(f'Messages/{message_id}/cr_report_count').get()
        
        ref = db.reference(f'Messages/{message_id}')
        ref.update({
            f'cr_reports/{num_cr_reports + 1}': report,
            'cr_report_count': num_cr_reports + 1
        })

    def add_prompt(self, prompt_id, message_id):
        '''
        Given the message ID of a prompt and the ID of the original message, add the information to the database.
        '''
        ref = db.reference(f'/')
        ref.update({
            f'Prompts/{prompt_id}': message_id
        })
    
    def get_message_from_prompt(self, prompt_id):
        '''
        Given the message ID of a prompt, return the original message corresponding to it.
        '''
        ref = db.reference(f'Prompts/{prompt_id}')
        return ref.get()

    def remove_prompt(self, prompt_id):
        '''
        Given the message ID of a prompt, remove it from the database.
        '''
        ref = db.reference(f'Prompts/{prompt_id}')
        ref.delete()

    def get_cr_reports(self, message_id):
        '''
        Given the message ID of the original message, retrieve its content reviewer reports.
        '''
        ref = db.reference(f'Messages/{message_id}')
        return ref.get()
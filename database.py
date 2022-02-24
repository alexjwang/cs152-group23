import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

class Database:

    def __init__(self):
        cred = credentials.Certificate('firebase-sdk.json')
        firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://cs-152-group-23-default-rtdb.firebaseio.com/'
        })

    def create_message_record(self, messageID):
        '''
        Given a message ID, create a new record for its reports in the database.
        '''
        ref = db.reference('/')
        ref.update({
            f'Messages/{messageID}': {
                'reports': {},
                'cr_report_count': 0,
                'non_severe_count': 0
            },
        })
    
    def add_report(self, messageID, report):
        '''
        Given a content reviewer report containing author, time, and description, adds the report to the database.
        '''
        num_cr_reports = db.reference(f'Messages/{messageID}/cr_report_count').get()
        if num_cr_reports is None:
            self.create_message_record(messageID)
            num_cr_reports = db.reference(f'Messages/{messageID}/cr_report_count').get()
        
        ref = db.reference(f'Messages/{messageID}')
        ref.update({
            f'reports/{str(num_cr_reports + 1)}': report,
            'cr_report_count': num_cr_reports + 1
        })
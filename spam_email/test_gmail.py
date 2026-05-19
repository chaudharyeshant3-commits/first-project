from gmail_service import GmailService
from app import app, db

with app.app_context():
    g = GmailService()
    print("Is Auth:", g.is_authenticated())
    emails = g.fetch_new_emails()
    print("Emails:", len(emails))

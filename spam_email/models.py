from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Email(db.Model):
    __tablename__ = 'emails'

    id = db.Column(db.Integer, primary_key=True)
    gmail_id = db.Column(db.String(100), unique=True, nullable=False)
    subject = db.Column(db.String(500), default='(No Subject)')
    sender = db.Column(db.String(300), default='Unknown')
    sender_email = db.Column(db.String(300), default='')
    snippet = db.Column(db.Text, default='')
    category = db.Column(db.String(50), default='Unknown')
    category_icon = db.Column(db.String(10), default='📧')
    confidence = db.Column(db.Integer, default=0)
    risk_level = db.Column(db.String(20), default='Unknown')
    keywords_found = db.Column(db.Text, default='[]')
    suspicious_links = db.Column(db.Text, default='[]')
    has_dangerous_attachment = db.Column(db.Boolean, default=False)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'subject': self.subject,
            'sender': self.sender,
            'sender_email': self.sender_email,
            'snippet': self.snippet,
            'category': self.category,
            'category_icon': self.category_icon,
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'keywords_found': json.loads(self.keywords_found or '[]'),
            'suspicious_links': json.loads(self.suspicious_links or '[]'),
            'has_dangerous_attachment': self.has_dangerous_attachment,
            'received_at': self.received_at.strftime('%b %d, %H:%M') if self.received_at else '',
        }

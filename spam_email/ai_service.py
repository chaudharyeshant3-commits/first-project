import json
import re

class AIAssistant:
    def __init__(self):
        # No external API required; chatbot is always ready
        self.is_ready = True
        
    def generate_response(self, query, context_str=""):
        try:
            context = json.loads(context_str) if context_str else {}
        except Exception:
            context = {}
            
        q = query.lower()
        
        # Extract context data safely
        website_info = context.get('website_info', {})
        recent_emails = context.get('recent_emails', [])
        stats = website_info.get('category_statistics', {})
        total_emails = website_info.get('total_emails_analyzed', 0)
        
        # Rule 1: Summary or general stats
        if any(word in q for word in ['summary', 'stats', 'statistics', 'overview', 'dashboard']):
            spam_count = stats.get('Spam', 0)
            phishing_count = stats.get('Phishing', 0)
            work_count = stats.get('Work', 0)
            return (f"**Dashboard Summary:**\n"
                    f"- **Total Emails:** {total_emails}\n"
                    f"- **Spam:** {spam_count}\n"
                    f"- **Phishing:** {phishing_count}\n"
                    f"- **Work:** {work_count}\n\n"
                    f"*Your inbox is currently being monitored in real-time.*")
            
        # Rule 2: Specific categories (Spam, Phishing, etc.)
        for category in ['Spam', 'Phishing', 'Marketing', 'Newsletter', 'Personal', 'Work', 'Transaction']:
            if category.lower() in q:
                count = stats.get(category, 0)
                return f"You currently have **{count}** emails categorized as **{category}**."
                
        # Rule 3: Recent emails
        if any(word in q for word in ['recent', 'latest', 'new', 'last']):
            if not recent_emails:
                return "I don't see any recent emails in your inbox."
            res = "**Your most recent emails:**\n\n"
            for i, email in enumerate(recent_emails[:3], 1):
                subject = email.get('subject', 'No Subject')
                sender = email.get('sender', 'Unknown')
                category = email.get('category', 'None')
                res += f"{i}. **{subject}**\n   *From: {sender} | Category: {category}*\n\n"
            return res.strip()
            
        # Rule 4: Total emails
        if 'how many' in q and ('total' in q or 'emails' in q):
            return f"I have analyzed a total of **{total_emails}** emails for you."
            
        # Rule 5: About the app
        if any(word in q for word in ['what', 'who', 'about', 'help', 'do you do']):
            app_name = website_info.get('app_name', 'MailGuard')
            desc = website_info.get('description', 'I help you analyze your inbox locally.')
            return f"I am the **{app_name}** local assistant. {desc}"
            
        # Fallback response
        return "I am a fast, local assistant. Try asking me for a **summary**, your **recent emails**, or **how many spam** emails you have!"

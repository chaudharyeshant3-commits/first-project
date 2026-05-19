import json
from ai_service import AIAssistant

assistant = AIAssistant()
print(f"Is ready? {assistant.is_ready}")

context_data = {
    'website_info': {
        'app_name': 'MailGuard',
        'description': 'Real-time inbox intelligence and email categorization dashboard.',
        'total_emails_analyzed': 150,
        'category_statistics': {'Spam': 10, 'Phishing': 2, 'Work': 50, 'Personal': 80},
    },
    'recent_emails': [
        {'subject': 'Meeting at 10', 'sender': 'boss@work.com', 'category': 'Work'},
        {'subject': 'Win $1000 now!', 'sender': 'spam@spam.com', 'category': 'Spam'}
    ]
}

context_str = json.dumps(context_data)

queries = [
    "What is my dashboard summary?",
    "How many spam emails do I have?",
    "Show me my recent emails",
    "How many total emails?",
    "What do you do?",
    "Random unhandled query"
]

for q in queries:
    print(f"\n--- Query: {q} ---")
    print(assistant.generate_response(q, context_str))

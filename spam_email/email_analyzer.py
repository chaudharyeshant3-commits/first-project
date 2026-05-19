import re
from urllib.parse import urlparse

# ── Keyword Databases ──────────────────────────────────────────────────────────

SPAM_HIGH = [
    'you have won','winner','lottery','prize money','claim your prize',
    'free money','earn money fast','nigerian prince','inheritance funds',
    'wire transfer','western union','moneygram','jackpot','million dollars',
    'no credit check','pre-approved loan','risk free','guaranteed income',
    'crypto profit','bitcoin profit','double your money','lose weight fast',
    'diet supplement','cheap medication','viagra','cialis','online pharmacy',
    'congratulations you','dear beneficiary','selected for a prize',
]
SPAM_MED = [
    'click here now','act now','limited time offer','special promotion',
    'you are a winner','free gift','no obligation','100% free',
    'earn extra cash','passive income','financial freedom','work from home',
]
PHISH_HIGH = [
    'verify your account immediately','account has been suspended',
    'unusual activity detected','suspicious activity','click to verify your account',
    'update your payment information','social security number','bank account details',
    'login credentials','your account will be closed','action required immediately',
    'verify now or account will be deleted','your paypal account',
    'your apple id has been','microsoft account suspended','google account suspended',
    'netflix account suspended',
]
PHISH_MED = [
    'verify your information','confirm your email','update your account',
    'account verification needed','security check required',
    'unauthorized access attempt','we noticed unusual','immediate response required',
]
VIRUS_KW = [
    'enable macros','enable editing','enable content',
    'run this program','download and execute','install this file',
]
DANGEROUS_EXT = ['.exe','.bat','.vbs','.scr','.msi','.cmd','.ps1','.jar','.hta','.pif','.reg']

MARKETING_HIGH = [
    'unsubscribe','view in browser','special offer','flash sale','mega sale',
    '% off','save up to','free shipping','use code','promo code','coupon code',
    'shop now','order today','black friday','cyber monday','new arrivals',
]
MARKETING_MED = [
    'sale ends','today only','weekend only','vip access','early access',
    'while supplies last','limited stock','recommended for you',
]
NEWSLETTER_KW = [
    'newsletter','weekly digest','monthly digest','weekly roundup','issue #',
    'edition #','curated for you','top stories','briefing','bulletin','recap',
]
TRANSACTION_KW = [
    'order confirmation','order #','purchase confirmation','payment received',
    'payment successful','invoice attached','receipt for','has been shipped',
    'tracking number','out for delivery','delivered','subscription renewal',
    'booking confirmation','reservation confirmed','ticket confirmation',
]
NOTIFICATION_KW = [
    'do not reply','automated message','this is an automated',
    'you have a new message','commented on your','liked your',
    'new login','sign-in from','new device',
]
WORK_KW = [
    'meeting','agenda','action items','follow up','project update',
    'deadline','proposal','contract','please find attached','as discussed',
    'best regards','warm regards','looking forward to','quarterly','annual report',
]
FREE_DOMAINS = {'gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','icloud.com','protonmail.com'}

ICONS = {
    'Spam': '🚫',
    'Virus / Malware': '🦠',
    'Phishing': '🎣',
    'Marketing': '📢',
    'Newsletter': '📰',
    'Transaction': '📦',
    'Notification': '🔔',
    'Work': '💼',
    'Personal': '👤',
}

class EmailAnalyzer:
    def analyze(self, email_data):
        subject = (email_data.get('subject') or '').lower()
        body = (email_data.get('body') or email_data.get('snippet') or '').lower()
        sender_email = (email_data.get('sender_email') or '').lower()
        attachments = email_data.get('attachments', [])
        list_id = email_data.get('list_id', '')
        list_unsub = email_data.get('list_unsubscribe', '')
        labels = email_data.get('labels', [])
        text = f"{subject} {body}"
        scores = {}
        found = []

        # Boost scores based on Gmail's built-in labels
        if 'SPAM' in labels:
            scores['Spam'] = 100
            found.append('gmail_spam_label')
        if 'CATEGORY_PROMOTIONS' in labels:
            scores['Marketing'] = 80
        if 'CATEGORY_UPDATES' in labels:
            scores['Transaction'] = 50
            scores['Notification'] = 50
        if 'CATEGORY_PERSONAL' in labels:
            scores['Personal'] = 80
        if 'IMPORTANT' in labels:
            scores['Work'] = scores.get('Work', 0) + 15  # Reduced from 40 as it is too generic

        # Virus – dangerous attachments
        bad_att = [a for a in attachments if any(a.lower().endswith(e) for e in DANGEROUS_EXT)]
        if bad_att:
            scores['Virus / Malware'] = 95
            found += [f'Dangerous attachment: {a}' for a in bad_att]
        for kw in VIRUS_KW:
            if kw in text:
                scores['Virus / Malware'] = max(scores.get('Virus / Malware', 0) + 30, 60)
                found.append(kw)

        # Suspicious links
        susp_links = self._suspicious_links(body)
        if susp_links:
            scores['Phishing'] = scores.get('Phishing', 0) + 25

        # Spam
        s = scores.get('Spam', 0)
        s += sum(15 for kw in SPAM_HIGH if kw in text and not found.append(kw))
        s += sum(8 for kw in SPAM_MED if kw in text and not found.append(kw))
        scores['Spam'] = min(s, 100)

        # Phishing
        p = sum(20 for kw in PHISH_HIGH if kw in text and not found.append(kw))
        p += sum(10 for kw in PHISH_MED if kw in text and not found.append(kw))
        scores['Phishing'] = min(scores.get('Phishing', 0) + p, 100)

        # Marketing
        m = scores.get('Marketing', 0)
        m += 40 if list_unsub else 0
        if list_unsub: found.append('unsubscribe header')
        m += sum(12 for kw in MARKETING_HIGH if kw in text and not found.append(kw))
        m += sum(6 for kw in MARKETING_MED if kw in text and not found.append(kw))
        scores['Marketing'] = min(m, 100)

        # Newsletter
        n = 50 if list_id else 0
        if list_id: found.append('list-id header')
        n += sum(15 for kw in NEWSLETTER_KW if kw in text and not found.append(kw))
        scores['Newsletter'] = min(n, 100)

        # Transaction
        t = scores.get('Transaction', 0)
        t += sum(15 for kw in TRANSACTION_KW if kw in text and not found.append(kw))
        scores['Transaction'] = min(t, 100)

        # Notification
        no = scores.get('Notification', 0)
        if any(x in sender_email for x in ['noreply','no-reply','donotreply']):
            no += 40; found.append('no-reply sender')
        no += sum(15 for kw in NOTIFICATION_KW if kw in text and not found.append(kw))
        scores['Notification'] = min(no, 100)

        # Work
        w = scores.get('Work', 0)
        w += sum(12 for kw in WORK_KW if kw in text and not found.append(kw))
        if sender_email and '@' in sender_email:
            domain = sender_email.split('@')[1]
            if domain not in FREE_DOMAINS: w += 15
        scores['Work'] = min(w, 100)

        scores['Personal'] = 30

        if max(scores.values(), default=0) < 25:
            category, confidence = 'Personal', 60
        else:
            category = max(scores, key=scores.get)
            confidence = min(scores[category], 99)

        return {
            'category': category,
            'icon': ICONS.get(category, '📧'),
            'confidence': confidence,
            'risk_level': self._risk(category, confidence),
            'keywords_found': list(dict.fromkeys(found))[:10],
            'suspicious_links': susp_links[:5],
            'has_dangerous_attachment': bool(bad_att),
        }

    def _suspicious_links(self, body):
        urls = re.findall(r'https?://[^\s<>"\']+', body)
        bad_tlds = ['.tk','.ml','.ga','.cf','.gq','.xyz','.click']
        ip_re = re.compile(r'https?://\d+\.\d+\.\d+\.\d+')
        result = []
        for url in urls:
            try:
                domain = urlparse(url).netloc.lower()
                if ip_re.match(url) or any(domain.endswith(t) for t in bad_tlds) or len(url) > 200:
                    result.append(url)
            except Exception:
                pass
        return result

    def _risk(self, category, confidence):
        if category in ('Virus / Malware', 'Phishing') and confidence >= 60: return 'Critical'
        if category in ('Virus / Malware', 'Phishing'): return 'High'
        if category == 'Spam' and confidence >= 70: return 'High'
        if category == 'Spam': return 'Medium'
        if category == 'Marketing': return 'Low'
        return 'Safe'

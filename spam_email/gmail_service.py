import os, json, base64, re
from datetime import datetime
from email.utils import parsedate_to_datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
HISTORY_FILE = 'last_history.json'
REDIRECT_URI = 'http://localhost:5000/oauth2callback'


class GmailService:
    def __init__(self):
        self.service = None
        self.user_email = None
        self.auth_flow = None
        self._load_token()

    def _load_token(self):
        if not os.path.exists(TOKEN_FILE):
            return
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
            creds = Credentials.from_authorized_user_info(data, SCOPES)
            if creds.valid:
                self.service = build('gmail', 'v1', credentials=creds)
                self._get_user_info()
            elif creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_token(creds)
                self.service = build('gmail', 'v1', credentials=creds)
                self._get_user_info()
        except Exception as e:
            print(f'Token load error: {e}')

    def _save_token(self, creds):
        with open(TOKEN_FILE, 'w') as f:
            json.dump({
                'token': creds.token, 'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri, 'client_id': creds.client_id,
                'client_secret': creds.client_secret, 'scopes': list(creds.scopes or [])
            }, f)

    def _get_user_info(self):
        try:
            p = self.service.users().getProfile(userId='me').execute()
            self.user_email = p.get('emailAddress', '')
        except Exception:
            pass

    def is_authenticated(self):
        return self.service is not None

    def get_user_email(self):
        return self.user_email or 'Connected'

    def get_auth_url(self):
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError('credentials.json not found!')
        self.auth_flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        url, _ = self.auth_flow.authorization_url(access_type='offline', prompt='consent')
        return url

    def exchange_code(self, code):
        if not hasattr(self, 'auth_flow') or not self.auth_flow:
            self.auth_flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        self.auth_flow.fetch_token(code=code)
        creds = self.auth_flow.credentials
        self._save_token(creds)
        self.service = build('gmail', 'v1', credentials=creds)
        self._get_user_info()

    def logout(self):
        self.service = None
        self.user_email = None
        for f in [TOKEN_FILE, HISTORY_FILE]:
            if os.path.exists(f): os.remove(f)

    def _last_history_id(self):
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                return json.load(f).get('history_id')
        return None

    def _save_history_id(self, hid):
        with open(HISTORY_FILE, 'w') as f:
            json.dump({'history_id': hid}, f)

    def fetch_new_emails(self):
        if not self.service: return []
        try:
            last_hid = self._last_history_id()
            return self._initial_fetch() if last_hid is None else self._incremental_fetch(last_hid)
        except Exception as e:
            print(f'Fetch error: {e}')
            return []

    def _initial_fetch(self):
        try:
            result = self.service.users().messages().list(userId='me', q="-in:sent -in:draft -in:trash", maxResults=50).execute()
            profile = self.service.users().getProfile(userId='me').execute()
            self._save_history_id(profile.get('historyId'))
            emails = []
            for msg in (result.get('messages') or []):
                data = self._get_email_data(msg['id'])
                if data: emails.append(data)
            return emails
        except Exception as e:
            print(f'Initial fetch error: {e}')
            return []

    def _incremental_fetch(self, start_hid):
        try:
            hr = self.service.users().history().list(
                userId='me', startHistoryId=start_hid,
                historyTypes=['messageAdded']
            ).execute()
            self._save_history_id(hr.get('historyId', start_hid))
            ids = []
            for record in hr.get('history', []):
                for ma in record.get('messagesAdded', []):
                    msg = ma.get('message', {})
                    labels = msg.get('labelIds', [])
                    if 'SENT' not in labels and 'DRAFT' not in labels and 'TRASH' not in labels:
                        ids.append(msg['id'])
            emails = []
            for mid in ids:
                data = self._get_email_data(mid)
                if data: emails.append(data)
            return emails
        except HttpError as e:
            if e.resp.status in (404, 400):
                if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
                return self._initial_fetch()
            raise

    def _get_email_data(self, msg_id):
        try:
            msg = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
            from_hdr = headers.get('from', 'Unknown')
            m = re.search(r'<(.+?)>', from_hdr)
            sender_email = m.group(1) if m else (from_hdr if '@' in from_hdr else '')
            sender_name = from_hdr[:from_hdr.find('<')].strip().strip('"') if m else sender_email
            try:
                received_at = parsedate_to_datetime(headers.get('date', ''))
            except Exception:
                received_at = datetime.utcnow()
            return {
                'id': msg_id,
                'subject': headers.get('subject', '(No Subject)'),
                'sender': sender_name or sender_email,
                'sender_email': sender_email,
                'snippet': msg.get('snippet', ''),
                'body': self._extract_body(msg.get('payload', {})),
                'date': received_at,
                'list_id': headers.get('list-id', ''),
                'list_unsubscribe': headers.get('list-unsubscribe', ''),
                'attachments': self._get_attachments(msg.get('payload', {})),
                'labels': msg.get('labelIds', []),
            }
        except Exception as e:
            print(f'Error fetching {msg_id}: {e}')
            return None

    def _extract_body(self, payload):
        body = ''
        if payload.get('body', {}).get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        for part in payload.get('parts', []):
            mt = part.get('mimeType', '')
            if mt == 'text/plain' and part.get('body', {}).get('data'):
                body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
            elif mt == 'text/html' and not body and part.get('body', {}).get('data'):
                html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                body += re.sub(r'<[^>]+>', ' ', html)
            elif part.get('parts'):
                body += self._extract_body(part)
        return body[:5000]

    def _get_attachments(self, payload):
        result = []
        for part in payload.get('parts', []):
            if part.get('filename'): result.append(part['filename'])
            elif part.get('parts'): result.extend(self._get_attachments(part))
        return result

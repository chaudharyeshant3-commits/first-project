import os, json, threading, time, sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO
from models import db, Email
from gmail_service import GmailService
from email_analyzer import EmailAnalyzer
from ai_service import AIAssistant

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*', logger=False, engineio_logger=False)

gmail = GmailService()
analyzer = EmailAnalyzer()
ai_assistant = AIAssistant()

polling_active = False
polling_lock = threading.Lock()


def background_poll():
    global polling_active
    print('📧 Polling started – checking every 30s')
    with app.app_context():
        while polling_active:
            try:
                new_emails = gmail.fetch_new_emails()
                for ed in new_emails:
                    if Email.query.filter_by(gmail_id=ed['id']).first():
                        continue
                    analysis = analyzer.analyze(ed)
                    email = Email(
                        gmail_id=ed['id'],
                        subject=ed.get('subject', '(No Subject)'),
                        sender=ed.get('sender', 'Unknown'),
                        sender_email=ed.get('sender_email', ''),
                        snippet=ed.get('snippet', ''),
                        category=analysis['category'],
                        category_icon=analysis['icon'],
                        confidence=analysis['confidence'],
                        risk_level=analysis['risk_level'],
                        keywords_found=json.dumps(analysis['keywords_found']),
                        suspicious_links=json.dumps(analysis['suspicious_links']),
                        has_dangerous_attachment=analysis['has_dangerous_attachment'],
                        received_at=ed.get('date', datetime.utcnow()),
                    )
                    db.session.add(email)
                    db.session.commit()
                    socketio.emit('new_email', {
                        **email.to_dict(),
                        'keywords_found': analysis['keywords_found'],
                    })
                    print(f'✉  {email.subject[:40]} → {email.category} ({email.confidence}%)')
            except Exception as e:
                print(f'⚠  Poll error: {e}')
            time.sleep(30)
    print('🛑 Polling stopped')


def start_polling():
    global polling_active
    with polling_lock:
        if not polling_active:
            polling_active = True
            t = threading.Thread(target=background_poll, daemon=True)
            t.start()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/dashboard')
def dashboard():
    if not gmail.is_authenticated():
        return redirect(url_for('login'))
    emails = Email.query.order_by(Email.received_at.desc()).limit(500).all()
    by_cat = db.session.query(Email.category, db.func.count(Email.id)).group_by(Email.category).all()
    stats = {cat: cnt for cat, cnt in by_cat}
    by_risk = db.session.query(Email.risk_level, db.func.count(Email.id)).group_by(Email.risk_level).all()
    risk_stats = {r: cnt for r, cnt in by_risk}
    return render_template('index.html', emails=emails, stats=stats, risk_stats=risk_stats,
                           total=Email.query.count(), user_email=gmail.get_user_email())


@app.route('/login')
def login():
    if gmail.is_authenticated():
        return redirect(url_for('dashboard'))
    creds_missing = not os.path.exists('credentials.json')
    return render_template('login.html', creds_missing=creds_missing)


@app.route('/connect')
def connect():
    try:
        return redirect(gmail.get_auth_url())
    except FileNotFoundError:
        return redirect(url_for('login'))


@app.route('/oauth2callback')
def oauth2callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('login'))
    try:
        gmail.exchange_code(code)
        start_polling()
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f'OAuth error: {e}')
        return redirect(url_for('login', error=str(e)))


@app.route('/logout')
def logout():
    global polling_active
    polling_active = False
    gmail.logout()
    return redirect(url_for('login'))


@app.route('/api/emails')
def api_emails():
    emails = Email.query.order_by(Email.received_at.desc()).limit(500).all()
    return jsonify([e.to_dict() for e in emails])


@app.route('/api/stats')
def api_stats():
    by_cat = db.session.query(Email.category, db.func.count(Email.id)).group_by(Email.category).all()
    by_risk = db.session.query(Email.risk_level, db.func.count(Email.id)).group_by(Email.risk_level).all()
    return jsonify({
        'total': Email.query.count(), 
        'by_category': {c: n for c, n in by_cat},
        'by_risk': {r: cnt for r, cnt in by_risk}
    })


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    message = data.get('message', '')
    
    total_emails = Email.query.count()
    by_cat = db.session.query(Email.category, db.func.count(Email.id)).group_by(Email.category).all()
    stats = {cat: cnt for cat, cnt in by_cat}
    by_risk = db.session.query(Email.risk_level, db.func.count(Email.id)).group_by(Email.risk_level).all()
    risk_stats = {r: cnt for r, cnt in by_risk}

    # Get last 20 emails for context
    emails = Email.query.order_by(Email.received_at.desc()).limit(20).all()
    recent_emails = [
        {
            'subject': e.subject,
            'sender': e.sender,
            'category': e.category,
            'risk': e.risk_level,
            'snippet': e.snippet
        } for e in emails
    ]
    
    context_data = {
        'website_info': {
            'app_name': 'MailGuard',
            'description': 'Real-time inbox intelligence and email categorization dashboard.',
            'total_emails_analyzed': total_emails,
            'category_statistics': stats,
            'risk_level_statistics': risk_stats,
        },
        'recent_emails': recent_emails
    }
    context_str = json.dumps(context_data)
    
    response = ai_assistant.generate_response(message, context_str)
    return jsonify({'response': response})


@socketio.on('connect')
def on_connect():
    print('🔌 WebSocket client connected')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    if gmail.is_authenticated():
        start_polling()
    socketio.run(app, host='0.0.0.0', debug=True, port=5000, use_reloader=False)

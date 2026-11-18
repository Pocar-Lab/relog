"""
User authetication system to signup, login, and logout.

Reference: https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from pathlib import Path
from secrets import compare_digest, token_bytes, token_urlsafe
import sqlite3
from tempfile import NamedTemporaryFile


auth = Blueprint('auth', __name__)
ACCOUNT_PAGE_TITLE = 'PocarLab Logbook'
ACCENT_OPTIONS = {
    'neutral': 'Default',
    'blue': 'Blue',
    'teal': 'Teal',
    'plum': 'Plum',
    'rust': 'Rust',
    'green': 'Green',
    'gold': 'Gold',
    'indigo': 'Indigo',
    'rose': 'Rose',
    'slate': 'Slate',
}

def session_key(instance_path):
    configured = os.environ.get("RELOG_SECRET_KEY")
    if configured:
        return configured

    key_file = Path(instance_path) / "session-key"
    if not key_file.exists():
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=key_file.parent) as generated:
            generated.write(token_bytes(32))
            generated.flush()
            try:
                os.link(generated.name, key_file)
            except FileExistsError:
                pass
    return key_file.read_bytes()


class User(UserMixin):
    def __init__(self, name, user, email, active=False, accent='neutral', show_archived=False):
        self.name = name
        self.user = user
        self.email = email
        self.active = active
        self.accent = accent if accent in ACCENT_OPTIONS else 'neutral'
        self.show_archived = bool(show_archived)

    def is_active(self):
        return self.active

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    def get_id(self):
        return self.user

# TODO import from logbook.py
def get_db():
    conn = sqlite3.connect('logbook.db')
    conn.row_factory = sqlite3.Row # Support row access by column name
    return conn

@auth.route('/login')
def login():
    return render_template('login.html', title=ACCOUNT_PAGE_TITLE, sections={})

@auth.post('/login')
def login_post():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    # remember = True if request.form.get('remember') else False

    with get_db() as conn:
        user = conn.execute("SELECT * FROM people WHERE user = ? OR email = ?", (email, email)).fetchone()

    if not user or not password or not check_password_hash(user['password'], password):
        flash('Please check your username or email and password, then try again.')
        destination = 'home' if request.form.get('from_home') == '1' else 'auth.login'
        return redirect(url_for(destination))

    u = User(
        user['name'], user['user'], user['email'],
        active=user['role'] != 'pending', accent=user['accent'], show_archived=user['show_archived'],
    )
    login_user(u, remember=True)
    # TODO redirect to previous page found in 'next' param
    return redirect('/')

@auth.route('/signup')
def signup():
    return render_template('signup.html', title=ACCOUNT_PAGE_TITLE, sections={})

@auth.post('/signup')
def signup_post():
    name = request.form.get('name', '').strip()
    user = request.form.get('user', '').lower()
    email = request.form.get('email', '').strip().lower() # TODO validate
    password = request.form.get('password', '').strip()

    if not all((name, user, email, password)):
        flash('Fill in all fields to register.')
        return redirect(url_for('auth.signup'))

    if any(character.isspace() for character in user):
        flash('Username must not contain spaces')
        return redirect(url_for('auth.signup'))
    if not user.isalnum():
        flash('Username can only contain letters and numbers.')
        return redirect(url_for('auth.signup'))

    password_hash = generate_password_hash(password)
    with get_db() as conn:
        result = conn.execute(
            "INSERT INTO people (user, name, email, password) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (user, name, email, password_hash),
        )
    if result.rowcount == 0:
        flash('That username or email address is already in use.')
        return redirect(url_for('auth.signup'))

    return redirect(url_for('auth.login'))

def validate_account_form():
    token = session.get('account_form_token')
    submitted_token = request.form.get('account_form_token', '')
    if not token or not compare_digest(token.encode(), submitted_token.encode()):
        abort(400, 'Reload account settings and try again.')


@auth.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        validate_account_form()
        accent = request.form.get('accent')
        if accent not in ACCENT_OPTIONS:
            abort(400, 'Choose an accent color.')
        show_archived = request.form.get('show_archived')
        if show_archived not in ('0', '1'):
            abort(400, 'Reload Settings and try again.')
        with get_db() as conn:
            conn.execute(
                "UPDATE people SET accent = ?, show_archived = ? WHERE user = ?",
                (accent, show_archived == '1', current_user.get_id()),
            )
        flash('Settings saved.')
        return redirect(url_for('auth.account'))

    if 'account_form_token' not in session:
        session['account_form_token'] = token_urlsafe(32)
    return render_template('account.html', title='Settings', accents=ACCENT_OPTIONS)


@auth.get('/account/website')
@login_required
def website_settings():
    return redirect(url_for('auth.account'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

"""
User authetication system to signup, login, and logout.

Reference: https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from enum import IntEnum
from functools import wraps


auth = Blueprint('auth', __name__)

# Strict heirarchy of increasing permissions
class Role(IntEnum):
   Pending = 0 # waiting to be approved by admin
   Guest   = 1 # readonly
   Member  = 2 # read/write
   Mod     = 3 # read/write/limited modify
   Admin   = 4 # read/write/modify

class User(UserMixin):
    def __init__(self, name, user, email, role=Role.Pending):
        self.name = name
        self.user = user
        self.email = email
        self.role = role

    @property
    def is_active(self):
       return True
    def is_anonymous(self):
        return False
    @property
    def is_authenticated(self):
        return True
    def get_id(self):
        return self.user

# TODO import from logbook.py
def get_db():
    conn = sqlite3.connect('logbook.db')
    conn.row_factory = sqlite3.Row # Support row access by column name
    return conn

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated: # Not logged in
                return redirect(url_for('auth.login'))
            if current_user.role < role:
                abort(403)  # Logged in, but not high enough clearance
            return f(*args, **kwargs)
        return wrapper
    return decorator


@auth.route('/login')
def login():
    return render_template('login.html', title="Login")

@auth.post('/login')
def login_post():
    email = request.form.get('email').strip().lower()
    password = request.form.get('password')
    # remember = True if request.form.get('remember') else False

    with get_db() as conn:
        user = conn.execute("SELECT * FROM people WHERE user = ? OR email = ?", (email, email)).fetchone()

    if not user or not check_password_hash(user['password'], password):
        flash('Please check your login details and try again.')
        return redirect(url_for('auth.login'))

    u = User(user['name'], user['user'], user['email'], user['role'])
    login_user(u, remember=True)
    # TODO redirect to previous page found in 'next' param
    return redirect('/')

@auth.route('/signup')
def signup():
    return render_template('signup.html', title="Signup")

@auth.post('/signup')
def signup_post():
    name = request.form.get('name').strip()
    user = request.form.get('user').strip().lower()
    email = request.form.get('email').strip().lower() # TODO validate
    password = request.form.get('password').strip()

    if ' ' in user:
        flash('Username must not contain spaces')
        return redirect(url_for('auth.signup'))
    if not user.isalpha():
        flash('Username must only contain alphabet letters')
        return redirect(url_for('auth.signup'))

    with get_db() as conn:
        person = conn.execute("SELECT * FROM people WHERE user = ? OR email = ?", (user, email)).fetchone()
    if person:
        flash('Email address or username already exists')
        return redirect(url_for('auth.signup'))

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO people (user, name, email, password) VALUES (?, ?, ?, ?)",
            (user, name, email, generate_password_hash(password)),
        )

    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

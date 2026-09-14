"""
Simple logbook for recording daily lab notes
Install: pip install flask flask-cors
Run:     python logbook.py
"""

from flask import Flask, request, jsonify, render_template, send_from_directory, redirect
from werkzeug.utils import secure_filename
from markupsafe import escape
from flask_cors import CORS
import datetime as dt
import sqlite3
import markdown
import os


app = Flask(__name__, static_folder='static', template_folder="pub")
CORS(app)  # Allow requests from the HTML file opened locally

DB_PATH = "logbook.db"

UPLOAD_FOLDER = 'static/upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS log (
                num     INTEGER PRIMARY KEY AUTOINCREMENT,
                date    TEXT    DEFAULT (datetime('now')),
                authors TEXT    NOT NULL,
                files   TEXT    DEFAULT NULL,
                note    TEXT    NOT NULL
            )
        """)

IMG_EXTS = {'png', 'apng', 'avif', 'jpg', 'jpeg', 'jfif',
            'pjpeg', 'pjp', 'jxl', 'gif', 'svg', 'webp'}

def is_file_img(filename):
    ext = filename.split('.')[-1].lower()
    return ext in IMG_EXTS
app.jinja_env.globals.update(is_file_img=is_file_img)

# Static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# TODO markdown to html files in wiki/

def inc_date(date, val=1):
    "Increment or decrement date by value given"
    delta = dt.timedelta(days=val)
    next_date = dt.date.strptime(date, "%Y-%m-%d") + delta
    return next_date.strftime("%Y-%m-%d")

# Home page
@app.route('/')
def home():
    num = request.args.get('num', '').strip() # TODO strip leading #
    author = request.args.get('author', '').strip()
    before = request.args.get('before', '').strip()
    after = request.args.get('after', '').strip()
    text = request.args.get('q', '').strip()

    # TODO pull out to func
    query = "SELECT * FROM log WHERE "
    title = "Logs "
    params = []
    if num:
        query += "num = ? AND " # TODO search range if hypen
        title += f"#{num} "
        params.append(num)
    if author:
        query += "authors = ? AND " # TODO any author in authors list
        title += f"by {author} "
        params.append(author)
    if before:
        query += "date(date) <= ? AND "
        params.append(before)
    if after:
        query += "date(date) >= ? AND "
        params.append(after)
    if text:
        query += "note LIKE ? AND " # TODO replace with MATCH
        title += f"containing '{text}' "
        params.append(f"%{text}%")
    query += " 1=1 ORDER BY num ASC"

    if before == after and before:
        title += f"on {before} " # TODO change to today when current date
    else:
        if before:
            title += f"before {before} "
        if after:
            title += f"after {after} "

    rows = get_db().execute(query, params).fetchall()
    curr_date = dt.datetime.now().strftime("%Y-%m-%d")
    prev_date = inc_date(before or curr_date, -1)
    next_date = inc_date(after or curr_date, +1)
    return render_template('index.html', logs=rows, title=title,
                           curr_date=curr_date, prev_date=prev_date, next_date=next_date)

# Upload new logbook post
@app.post('/log')
def log():
    name = request.form['name'].strip() # TODO split into multiple authors
    msg = request.form['message'].strip()
    date = f"{dt.datetime.now():%Y-%m-%d %H:%M}"

    files = request.files.getlist("files")
    # TODO dont override file of same name
    # TODO put in date folder
    # TODO compress image / block files over 2MB
    # TODO error if file name contains :
    file_names = []
    for file in files:
        file_name = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))
        file_names.append(file_name)
    file_str = ":".join(file_names)

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO log (date, authors, files, note) VALUES (?, ?, ?, ?)",
            (date, name, file_str, msg),
        )
        date_no_time = date.split(' ', 1)[0]
        # TODO on failure to upload file etc send warning pop up
        return redirect(f"/?before={date_no_time}&after={date_no_time}#{cur.lastrowid}")


if __name__ == "__main__":
    init_db()
    print("Server running → http://localhost:5000")
    app.run(debug=True, port=5000)

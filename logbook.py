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
from dateutil.parser import parse
import sqlite3
import markdown
import os
now = dt.datetime.now


app = Flask(__name__, static_folder='static', template_folder="pub")
CORS(app)  # Allow requests from the HTML file opened locally

DB_PATH = "logbook.db"

UPLOAD_FOLDER = 'static/upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

SECTIONS = [ 'borexino', 'darkside', 'exo', 'lxe', 'kumarlab', 'hfe', 'misc' ] # 'photosensor',

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Support row access by column name
    return conn

def init_db():
    with get_db() as conn:
        for sec in SECTIONS:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS log_{sec} (
                    num       INTEGER PRIMARY KEY AUTOINCREMENT,
                    authors   TEXT       NOT NULL,
                    date      TEXT       DEFAULT (datetime('now')),
                    submit    TEXT       DEFAULT (datetime('now')),
                    note      TEXT       NOT NULL,
                    files     TEXT       DEFAULT NULL,
                    crossout  tinyint(1) NOT NULL DEFAULT '0',
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
@app.route('/<string:sec>/log')
def logs(sec):
    if sec not in SECTIONS:
        abort(404)
    num = request.args.get('num', '').strip() # TODO strip leading #
    author = request.args.get('author', '').strip()
    before = request.args.get('before', '').strip()
    after = request.args.get('after', '').strip()
    text = request.args.get('q', '').strip()

    # TODO pull out to func
    query = f"SELECT * FROM log_{sec} WHERE "
    title = "Logs "
    params = []
    if num:
        # TODO change to anchor on date
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
    curr_date = now().strftime("%Y-%m-%d")
    prev_date = inc_date(before or curr_date, -1)
    next_date = inc_date(after or curr_date, +1)
    return render_template('index.html', logs=rows, title=title, sec=sec,
                           curr_date=curr_date, prev_date=prev_date, next_date=next_date)

def upload_files(sec, files):
    # TODO dont override file of same name
    # TODO put in date folder
    # TODO compress image / block files over 2MB
    # TODO error if file name contains :
    files_str = []
    for f in files:
        file_name = secure_filename(f.filename)
        if not file_name:
            continue
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], sec, file_name) # TODO date,
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        f.save(file_path)
        files_str.append(file_name)
    return ":".join(files_str)

# Upload new logbook post
@app.post('/<string:sec>/log')
def log(sec):
    if sec not in SECTIONS:
        abort(404)
    name = request.form['name'].strip() # TODO split into multiple authors
    msg = request.form['message'].strip()
    # TODO only set to now if datetime empty, otherwise error on parse exception
    try:
        date = parse(request.form['datetime'].strip())
    except:
        date = now()

    files = upload_files(sec, request.files.getlist("files"))

    with get_db() as conn:
        datestr = f"{date:%Y-%m-%d %H:%M}"
        cur = conn.execute(
            f"INSERT INTO log_{sec} (date, authors, files, note) VALUES (?, ?, ?, ?)",
            (datestr, name, files, msg),
        )
        date_no_time = f"{date:%Y-%m-%d}"
        # TODO on failure to upload file etc send warning pop up
        return redirect(f"/{sec}/log?before={date_no_time}&after={date_no_time}#{cur.lastrowid}")

@app.post('/<string:sec>/crossout/<int:num>')
def crossout(sec, num):
    "Mark the given log post as crossed out"
    if sec not in SECTIONS:
        abort(404)
    with get_db() as conn:
        conn.execute(f"UPDATE log_{sec} SET crossout = 1 WHERE num = ?", (num,))
    target = request.referrer or f'/?num={num}'
    return redirect(f"{target}#{num}")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

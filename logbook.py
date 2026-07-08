from flask import Flask, request, jsonify, render_template, send_from_directory
from markupsafe import escape
from flask_cors import CORS
import datetime as dt
import sqlite3
import markdown


app = Flask(__name__, static_folder='static', template_folder="pub")
CORS(app)  # Allow requests from the HTML file opened locally

DB_PATH = "logbook.db"

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
                note    TEXT    NOT NULL
            )
        """)


# Static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Home page
@app.route('/')
def home():
    num = request.args.get('num', '').strip() # TODO strip leading #
    author = request.args.get('author', '').strip()
    before = request.args.get('before', '').strip()
    after = request.args.get('after', '').strip()
    text = request.args.get('q', '').strip()

    query = "SELECT * FROM log WHERE "
    params = []
    if num:
        query += "num = ? AND " # TODO search range if hypen
        params.append(num)
    if author:
        query += "authors = ? AND " # TODO any author in authors list
        params.append(author)
    if before:
        query += "date <= ? AND "
        params.append(before)
    if after:
        query += "date >= ? AND "
        params.append(after)
    if text:
        query += "note LIKE ? AND " # TODO replace with MATCH
        params.append(f"%{text}%")
    query += " 1=1 ORDER BY num ASC"

    rows = get_db().execute(query, params).fetchall()
    return render_template('index.html', logs=rows)



# Upload new logbook post
@app.post('/log')
def log():
    name = request.form['name'].strip() # TODO split into multiple authors
    msg = request.form['message'].strip()
    date = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO log (date, authors, note) VALUES (?, ?, ?)",
            (date, name, msg),
        )
        # TODO get request of page w/ date
        return f"""
            <tr>
            <td>#{cur.lastrowid}</td>
            <td>{date}</td>
            <td>{escape(name)}</td>
            <td>{escape(msg)}</td>
            </tr>
        """

if __name__ == "__main__":
    init_db()
    print("Server running → http://localhost:5000")
    app.run(debug=True, port=5000)

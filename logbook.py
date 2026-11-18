"""
Simple logbook for recording daily lab notes
Install: pip install -r requirements.txt
Run:     python logbook.py
"""

from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, abort, url_for
from werkzeug.utils import secure_filename
from flask_cors import CORS
import datetime as dt
import re
from dateutil.parser import parse
import sqlite3
import markdown
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from tempfile import mkdtemp
from flask_login import LoginManager, current_user, login_required

from src.cal import count_days, month_view
from src.auth import ACCENT_OPTIONS, auth, session_key, User


app = Flask(__name__, static_folder='static', template_folder="pub")
CORS(app)  # Allow requests from the HTML file opened locally

app.config['SECRET_KEY'] = session_key(app.instance_path)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

app.register_blueprint(auth)

PUBLIC_ENDPOINTS = {'home', 'auth.login', 'auth.login_post', 'auth.signup', 'auth.signup_post'}
PUBLIC_ASSETS = {
    'theme.css', 'relog.css', 'lightbox3.css', 'lightbox3.min.js', 'signup.js',
    'umass-amherst-wordmark.png', 'umass-amherst-dark-logo.svg',
}


def is_public_asset():
    if request.endpoint in {'static', 'serve_static'}:
        asset = request.view_args.get('filename') or request.view_args.get('path')
        return asset in PUBLIC_ASSETS
    return False


@app.before_request
def require_sign_in():
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS or is_public_asset():
        return None
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


@app.after_request
def prevent_private_caching(response):
    if not is_public_asset():
        response.cache_control.no_store = True
    return response


DB_PATH = "logbook.db"

UPLOAD_FOLDER = 'static/upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

SECTIONS = {
    'borexino': 'Borexino',
    'darkside': 'DarkSide',
    'exo': 'EXO-200',
    'lxe': '021 LXe Lab',
    'kumar': '028 LXe Lab',
    'hfe': 'HFE System',
    'misc': 'Miscellaneous',
}
ARCHIVED_SECTIONS = {'borexino'}

def visible_sections(selected=None):
    if getattr(current_user, 'show_archived', False):
        return SECTIONS
    return {
        section: name for section, name in SECTIONS.items()
        if section not in ARCHIVED_SECTIONS or section == selected
    }

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Support row access by column name
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for sec in SECTIONS:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS log_{sec} (
                    num       INTEGER PRIMARY KEY AUTOINCREMENT,
                    authors   TEXT       NOT NULL,
                    date      INT        DEFAULT (unixepoch('now')),
                    inked     INT        DEFAULT (unixepoch('now')),
                    note      TEXT       NOT NULL,
                    files     TEXT       DEFAULT NULL,
                    crossout  tinyint(1) NOT NULL DEFAULT '0',
                    author_user TEXT
                )
            """)
            log_columns = {column["name"] for column in conn.execute(f"PRAGMA table_info(log_{sec})")}
            if "author_user" not in log_columns:
                conn.execute(f"ALTER TABLE log_{sec} ADD COLUMN author_user TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS people (
                user     TEXT NOT NULL PRIMARY KEY,
                name     TEXT NOT NULL,
                email    TEXT NOT NULL,
                password TEXT NOT NULL,
                joined   INT  DEFAULT (unixepoch('now')),
                role     TEXT NOT NULL DEFAULT 'pending',
                accent   TEXT NOT NULL DEFAULT 'neutral',
                show_archived INTEGER NOT NULL DEFAULT 0
            )
        """)

        people_columns = {column["name"] for column in conn.execute("PRAGMA table_info(people)")}
        if "accent" not in people_columns:
            conn.execute("ALTER TABLE people ADD COLUMN accent TEXT NOT NULL DEFAULT 'neutral'")
        if "show_archived" not in people_columns:
            conn.execute("ALTER TABLE people ADD COLUMN show_archived INTEGER NOT NULL DEFAULT 0")

        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS people_user_nocase ON people (user COLLATE NOCASE)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS people_email_nocase ON people (email COLLATE NOCASE)")
        except sqlite3.IntegrityError as error:
            raise RuntimeError(
                "The logbook database contains duplicate usernames or email addresses. "
                "Resolve the duplicate accounts before starting the logbook."
            ) from error

@login_manager.user_loader
def load_user(id):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM people WHERE user = (?)", [id]).fetchone()
    if user is None:
        return None
    return User(
        user['name'], user['user'], user['email'],
        active=user['role'] != 'pending', accent=user['accent'], show_archived=user['show_archived'],
    )


IMG_EXTS = {'png', 'apng', 'avif', 'jpg', 'jpeg', 'jfif',
            'pjpeg', 'pjp', 'jxl', 'gif', 'svg', 'webp'}

def is_file_img(filename):
    ext = filename.split('.')[-1].lower()
    return ext in IMG_EXTS
app.jinja_env.globals.update(is_file_img=is_file_img)

@app.template_filter('ts')
def fmt_ts(ts, fmt="%Y-%m-%d"):
    return dt.datetime.fromtimestamp(ts).strftime(fmt)

@app.template_filter('entry_reference')
def split_entry_reference(note):
    match = re.match(r"Re: #([0-9]+)(?=\r?\n|$)", note)
    if match:
        return match[1], note[match.end():]
    return None, note

def legacy_author_label(value):
    return ' '.join(value.split()).casefold()


def entries_with_author_accents(conn, rows):
    if not rows:
        return []

    by_user = {}
    colors_by_label = {}
    for person in conn.execute("SELECT user, name, accent FROM people"):
        accent = person['accent'] if person['accent'] in ACCENT_OPTIONS else 'neutral'
        name = person['name'].strip() or person['user']
        by_user[person['user']] = accent
        if accent != 'neutral':
            for label in (name, person['user']):
                colors_by_label.setdefault(legacy_author_label(label), set()).add(accent)

    # Entries saved before account attribution only have an author label.
    # Use the label's chosen color when there is no conflicting preference.
    by_label = {label: next(iter(colors)) for label, colors in colors_by_label.items() if len(colors) == 1}

    entries = []
    for row in rows:
        if row['author_user'] is None:
            accent = by_label.get(legacy_author_label(row['authors']), 'neutral')
        else:
            accent = by_user.get(row['author_user'], 'neutral')
        entries.append(dict(row, author_accent=accent))
    return entries


# Static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# TODO markdown to html files in wiki/

SEARCH_PAGE_SIZE = 25

def start_of_day(day):
    return int(dt.datetime.combine(day, dt.time.min).timestamp())

def search_query(query, section_keys, start, end):
    conditions = ["instr(lower(note), lower(?)) > 0"]
    values = [query]
    if start and start > dt.date.min:
        conditions.append("date >= ?")
        values.append(start_of_day(start))
    if end and end < dt.date.max:
        conditions.append("date < ?")
        values.append(start_of_day(end + dt.timedelta(days=1)))

    where = " AND ".join(conditions)
    selects = []
    params = []
    for key in section_keys:
        selects.append(
            f"SELECT ? AS section, num, authors, author_user, date, note, crossout FROM log_{key} WHERE {where}"
        )
        params.extend((key, *values))
    return " UNION ALL ".join(selects), params

# Home page
@app.route('/')
def home():
    if any(key in request.args for key in ('q', 'section', 'after', 'before')):
        filters = {key: request.args[key] for key in ('q', 'section', 'after', 'before', 'page')
                   if key in request.args}
        return redirect(url_for('search', **filters))

    current_time = dt.datetime.now().isoformat(timespec='minutes')
    return render_template('home.html', sections=visible_sections(), title='PocarLab Logbook', current_time=current_time)

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    section = request.args.get('section', '')
    after = request.args.get('after', '').strip()
    before = request.args.get('before', '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    has_filters = bool(query or section or after or before)

    if section and section not in SECTIONS:
        abort(400, 'Choose a logbook section.')

    sections = visible_sections(section)
    section_keys = (section,) if section else sections
    start = end = None
    filter_error = None
    try:
        start = dt.date.fromisoformat(after) if after else None
        end = dt.date.fromisoformat(before) if before else None
    except ValueError:
        filter_error = 'Enter valid dates for the period.'
    if start and end and end < start:
        filter_error = 'Choose an end date on or after the start date.'

    today = dt.date.today()
    calendar_date = start or end or today
    year = request.args.get('year', calendar_date.year, type=int)
    month = request.args.get('month', calendar_date.month, type=int)
    try:
        calendar = month_view(year, month)
    except (ValueError, OverflowError):
        abort(400, 'Choose a valid calendar month.')

    results = None
    has_more = False
    with get_db() as conn:
        calendar_sql, params = search_query(query, section_keys, calendar['first'], calendar['last'])
        calendar_counts = count_days(conn, calendar_sql, params)
        if has_filters and not filter_error:
            offset = (page - 1) * SEARCH_PAGE_SIZE
            if offset > 2**63 - 1:
                abort(400, 'Invalid results page.')
            sql, params = search_query(query, section_keys, start, end)
            rows = conn.execute(
                sql + " ORDER BY date DESC, section, num DESC LIMIT ? OFFSET ?",
                (*params, SEARCH_PAGE_SIZE + 1, offset),
            ).fetchall()
            results = entries_with_author_accents(conn, rows[:SEARCH_PAGE_SIZE])
            has_more = len(rows) > SEARCH_PAGE_SIZE

    return render_template('search.html', sections=sections, title='Search entries',
                           query=query, section=section, after=after, before=before,
                           calendar=calendar, calendar_counts=calendar_counts, today=today,
                           selected_day=start if start == end else None,
                           filter_error=filter_error, results=results, page=page, has_more=has_more)

def parse_date(date):
    try:
        return parse(date.strip())
    except (ValueError, AttributeError, OverflowError):
        return None

def date_title(before, after, fmt="%Y-%m-%d"):
    if not before and not after:
        return ""
    if not before:
        return f"since {after:{fmt}} "
    if not after:
        return f"until {before:{fmt}} "
    today = dt.datetime.now(before.tzinfo).date()
    if before.date() == today and after.date() == today:
        return "from Today "
    if before.date() == after.date():
        return f"from {before:{fmt}} "
    return f"from {after:{fmt}} to {before:{fmt}} "

HISTORY_PAGE_SIZE = 30


def entry_day(row):
    return dt.datetime.fromtimestamp(row['date']).date() if row['date'] is not None else None


def group_entry_days(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[entry_day(row)].append(row)
    return sorted(groups.items(), key=lambda group: group[0] or dt.date.min)


def entry_thread_numbers(conn, sec, reference):
    table = f"log_{sec}"
    parents = {}
    replies = defaultdict(list)
    for row in conn.execute(f"SELECT num, note FROM {table} WHERE note GLOB 'Re: #*'"):
        parent, _ = split_entry_reference(row['note'])
        if parent is not None:
            parent = parent.lstrip('0') or '0'
            child = str(row['num'])
            parents[child] = parent
            replies[parent].append(child)

    root = reference.lstrip('0') or '0'
    ancestors = set()
    while root in parents and root not in ancestors:
        ancestors.add(root)
        root = parents[root]

    # Use a set to include each reply once, even if legacy references form a cycle.
    thread_numbers = {root}
    pending = [root]
    while pending:
        for reply in replies.get(pending.pop(), ()):
            if reply not in thread_numbers:
                thread_numbers.add(reply)
                pending.append(reply)
    return root, thread_numbers


def load_entry_thread(conn, sec, reference):
    root, thread_numbers = entry_thread_numbers(conn, sec, reference)
    table = f"log_{sec}"
    rows = []
    numbers = list(thread_numbers)
    for offset in range(0, len(numbers), 500):
        batch = numbers[offset:offset + 500]
        placeholders = ', '.join('?' for _ in batch)
        rows.extend(conn.execute(f"SELECT * FROM {table} WHERE num IN ({placeholders})", batch))
    rows.sort(key=lambda row: (row['date'] is not None, row['date'] or 0, row['num']))

    original = None
    thread_replies = []
    for row in entries_with_author_accents(conn, rows):
        if str(row['num']) == root:
            original = row
        else:
            thread_replies.append(row)
    return root, original, thread_replies


@app.route('/<string:sec>/log/thread/<string:reference>')
@login_required
def entry_thread(sec, reference):
    if sec not in SECTIONS or not re.fullmatch(r'[0-9]+', reference):
        abort(404)

    with get_db() as conn:
        root, original, replies = load_entry_thread(conn, sec, reference)
    original_day = (entry_day(original), [original]) if original else None
    return render_template(
        'log.html', title=SECTIONS[sec], section=sec, sections=SECTIONS,
        history_title=f'Thread #{root}', thread_number=root, original_day=original_day,
        entry_days=group_entry_days(replies), current_time=dt.datetime.now().isoformat(timespec='minutes'),
    )


# Section logs
@app.route('/<string:sec>/log')
@login_required
def logs(sec):
    if sec not in SECTIONS:
        abort(404)
    num = request.args.get('num', '').strip() # TODO strip leading #
    author = request.args.get('author', '').strip()
    before_value = request.args.get('before', '').strip()
    after_value = request.args.get('after', '').strip()
    before = parse_date(before_value)
    after = parse_date(after_value)
    text = request.args.get('q', '').strip()

    period_error = None
    if (after_value and after is None) or (before_value and before is None):
        period_error = 'Enter valid dates for the period.'
    elif after and before and after.date() > before.date():
        period_error = 'Choose a Through date on or after the From date.'

    today = dt.date.today()
    has_period = bool(after_value or before_value)
    showing_history = not (num or author or text or has_period)
    older_than = request.args.get('older_than', type=int) if showing_history else None
    if older_than is not None and not 1 <= older_than <= 2**63 - 1:
        abort(400, 'Invalid entry history position.')

    history_title = "Entry " if num else "Entries "
    query = f"SELECT * FROM log_{sec} WHERE "
    params = []
    if has_period:
        query += "date IS NOT NULL AND "
    if num:
        # TODO change to anchor on date
        query += "num = ? AND " # TODO search range if hypen
        history_title += f"#{num} "
        params.append(num)
    if author:
        query += "authors = ? AND " # TODO any author in authors list
        history_title += f"by {author} "
        params.append(author)
    if before and before.date() < dt.date.max:
        query += "date < ? AND "
        end = before.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(1)
        params.append(int(end.timestamp()))
    if after and after.date() > dt.date.min:
        query += "date >= ? AND "
        start = after.replace(hour=0, minute=0, second=0, microsecond=0)
        params.append(int(start.timestamp()))
    if text:
        query += "note LIKE ? AND " # TODO replace with MATCH
        history_title += f"containing '{text}' "
        params.append(f"%{text}%")
    if older_than is not None:
        query += "num < ? AND "
        params.append(older_than)
    if showing_history and older_than is None:
        query += "date >= ? AND date < ? AND "
        params.extend((start_of_day(today), start_of_day(today + dt.timedelta(days=1))))
    if older_than is not None:
        query += "1=1 ORDER BY num DESC LIMIT ?"
        params.append(HISTORY_PAGE_SIZE)
    else:
        query += "1=1 ORDER BY date ASC, num ASC"

    rows = []
    if not period_error:
        with get_db() as conn:
            rows = entries_with_author_accents(conn, conn.execute(query, params).fetchall())

    if older_than is not None:
        rows.sort(key=lambda row: (row['date'] is not None, row['date'] or 0, row['num']))

    entry_days = group_entry_days(rows)

    first_day = (after or before).date() if after or before else today
    first_day = min((day for day, _ in entry_days if day is not None), default=first_day)
    if after:
        first_day = min(first_day, after.date())
    earlier_day = None
    if not period_error and first_day > dt.date.min:
        earlier_day = first_day - dt.timedelta(days=1)
    if showing_history or period_error:
        view_title = "Entry history"
    else:
        display_dates = date_title(before, after, fmt="%d %b %Y")
        view_title = (history_title + display_dates).strip()
    period_start = after.date() if after else None
    period_end = before.date() if before else None
    if not has_period:
        period_start = period_end = first_day
    return render_template('log.html', entry_days=entry_days, title=SECTIONS[sec], section=sec, sections=SECTIONS,
                           history_title=view_title, earlier_day=earlier_day,
                           view_day=today if showing_history and older_than is None else None,
                           current_time=dt.datetime.now().isoformat(timespec='minutes'),
                           period_start=period_start, period_end=period_end,
                           has_period=has_period, period_error=period_error)

def upload_files(sec, files, rollback):
    folder = Path(app.config['UPLOAD_FOLDER']) / sec
    filenames = []
    for upload in files:
        if not upload.filename:
            continue
        filename = secure_filename(upload.filename) or "attachment"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename
        try:
            output = path.open('xb')
        except FileExistsError:
            # Preserve the filename while giving the conflicting upload its own path.
            unique_folder = Path(mkdtemp(prefix="attachment-", dir=folder))
            rollback.callback(unique_folder.rmdir)
            path = unique_folder / filename
            output = path.open('xb')

        rollback.callback(path.unlink, missing_ok=True)
        with output:
            upload.save(output)
        filenames.append(path.relative_to(folder).as_posix())
    return ":".join(filenames)

def prepare_thread_reply(conn, sec, thread_number, message, reply_to):
    root, members = entry_thread_numbers(conn, sec, thread_number)
    if len(members) == 1 and conn.execute(f"SELECT 1 FROM log_{sec} WHERE num = ?", (root,)).fetchone() is None:
        abort(404, 'This thread could not be found.')

    reference, body = split_entry_reference(message)
    target = (reference or reply_to or root).lstrip('0') or '0'
    if target not in members:
        abort(400, 'Choose a reply target from this thread.')
    if not body.strip():
        abort(400, 'Reply text is required.')

    return root, f"Re: #{target}\n\n" + body.lstrip('\r\n')


# Upload new logbook post
@app.post('/', defaults={'sec': None})
@app.post('/<string:sec>/log')
@app.post('/<string:sec>/log/thread/<string:thread_number>')
@login_required
def log(sec, thread_number=None):
    if sec is None:
        sec = request.form.get('section')
        if sec not in SECTIONS:
            abort(400, 'Choose a logbook section.')
    elif sec not in SECTIONS:
        abort(404)

    author_names = [name for name in map(str.strip, request.form.get('author', '').split(',')) if name]
    authors = ', '.join(author_names) or current_user.name.strip() or current_user.get_id()
    msg = request.form.get('message', '').strip()
    if not msg:
        abort(400, 'Entry text is required.')
    if thread_number is not None and not re.fullmatch(r'[0-9]+', thread_number):
        abort(404)
    # TODO only set to now if datetime empty, otherwise error on parse exception
    # TODO if no time given replace with current time, not midnight
    entered_time = request.form.get('datetime', '').strip()
    date = parse_date(entered_time)
    if entered_time and date is None:
        abort(400, 'Enter a valid date and time.')
    timestamp = int((date or dt.datetime.now()).timestamp())

    with ExitStack() as rollback:
        with get_db() as conn:
            if thread_number is not None:
                thread_number, msg = prepare_thread_reply(conn, sec, thread_number, msg, request.form.get('reply_to'))
            files = upload_files(sec, request.files.getlist('files'), rollback)
            cur = conn.execute(
                f"INSERT INTO log_{sec} (date, authors, author_user, files, note) VALUES (?, ?, ?, ?, ?)",
                (timestamp, authors, current_user.get_id(), files, msg),
            )
            number = cur.lastrowid
        rollback.pop_all()

    if thread_number is not None:
        return redirect(url_for('entry_thread', sec=sec, reference=thread_number, _anchor=str(number)))

    entry_day = dt.datetime.fromtimestamp(timestamp).date()
    if entry_day != dt.date.today():
        return redirect(url_for('logs', sec=sec, after=entry_day, before=entry_day, _anchor=str(number)))
    return redirect(url_for('logs', sec=sec, _anchor=str(number)))

# Cross out log post number
@app.post('/<string:sec>/crossout/<int:num>')
@login_required
def crossout(sec, num):
    "Mark the given log post as crossed out"
    if sec not in SECTIONS:
        abort(404)
    with get_db() as conn:
        conn.execute(f"UPDATE log_{sec} SET crossout = 1 WHERE num = ?", (num,))
    if request.referrer:
        return redirect(f"{request.referrer}#{num}")
    return redirect(url_for('logs', sec=sec, num=num, _anchor=str(num)))

@app.route('/cal')
def cal():
    month = {key: request.args[key] for key in ('year', 'month') if key in request.args}
    return redirect(url_for('search', _anchor='search-calendar', **month))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

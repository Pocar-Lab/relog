import calendar
import datetime as dt


def month_view(year, month):
    first = dt.date(year, month, 1)
    last = first.replace(day=calendar.monthrange(year, month)[1])
    one_day = dt.timedelta(days=1)
    return {
        "first": first,
        "last": last,
        "previous": (first - one_day).replace(day=1) if first > dt.date.min else None,
        "next": last + one_day if last < dt.date.max else None,
        "weekdays": ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
        "weeks": calendar.Calendar(calendar.SUNDAY).monthdayscalendar(year, month),
    }


def count_days(conn, entries_sql, params):
    """Count matching entries by local day within one month."""
    rows = conn.execute(
        "SELECT CAST(strftime('%d', date, 'unixepoch', 'localtime') AS INTEGER) AS day, COUNT(*) AS total "
        f"FROM ({entries_sql}) GROUP BY day",
        params,
    )
    return {row["day"]: row["total"] for row in rows}

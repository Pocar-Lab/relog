from collections import Counter
import datetime as dt
import calendar

FIRST_WEEKDAY = 6 # Sunday

DAYS_OF_WEEK = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

def get_section_counts(conn, year, month, sections):
    """
    Returns {section: {day_of_month: count}} for the given month,
    querying each section's table for entries in that month.
    """
    counts = {}

    for section in sections:
        query = f"""
            SELECT date
            FROM log_{section}
            WHERE date >= ?
            AND   date <= ?
            GROUP BY date
        """
        if month < 12:
            next_month, next_year = (month + 1, year)
        else:
            next_month, next_year = (1, year + 1)
        month_range = (int(dt.datetime(year, month, 1).timestamp()),
                       int(dt.datetime(next_year, next_month, 1).timestamp()))
        logs = conn.execute(query, month_range)
        log_days = [dt.datetime.fromtimestamp(l['date']).day
                    for l in logs]
        counts[section] = dict(Counter(log_days))

    return counts

# TODO insert number of posts per day per sections
def cal_gen(conn, year, month, first_weekday, sections):
    res = '<table border="1" cellpadding="0" cellspacing="0">'

    # Header for days of week
    res += '<tr>'
    for i in range(len(DAYS_OF_WEEK)):
        day = DAYS_OF_WEEK[(first_weekday + i) % len(DAYS_OF_WEEK)]
        res += f'<th class="{day.lower()}">{day}</th>'
    res += '</tr>'

    # Fill in days
    calendar.setfirstweekday(first_weekday)
    days = calendar.monthcalendar(year, month)
    counts = get_section_counts(conn, year, month, sections.keys())
    for week in days:
        res += '<tr>'
        for day in week:
            day_disp = "&nbsp;" if day == 0 else day
            date_str = f"{year}-{month}-{day}"
            entries_html = ""
            # TODO sort by number in section
            for sec, sec_name in sections.items():
                num = counts[sec].get(day, 0)
                if num > 0:
                    entries_html += (
                        '<li>'
                            f'<a href="/{sec}/log?before={date_str}&amp;after={date_str}">'
                                f'<cal-sec>{sec_name}: </cal-sec>'
                                f'<cal-num>{num}</cal-num>'
                            '</a>'
                        '</li>'
                    )
            res += (
                '<td class="day">'
                f'<cal-day-num">{day_disp}</cal-day-num>'
                f'<cal-entries><ul>{entries_html}</ul></cal-entries>'
                '</td>'
            )

        res += '</tr>'

    res += "</table>"
    return res

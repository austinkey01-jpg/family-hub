"""Minimal iCalendar (.ics) reader with recurrence expansion. Standard library only.

Google Calendar, iCloud and Outlook all publish a private "secret address in iCal
format", so this one reader covers all three without OAuth.

Handles: VEVENT, all-day and timed events, TZID / UTC times, RRULE
(DAILY/WEEKLY/MONTHLY/YEARLY with INTERVAL, COUNT, UNTIL, BYDAY incl. "2TU"/"-1FR",
BYMONTHDAY), EXDATE, and RECURRENCE-ID overrides. That covers the vast majority of
family calendars. If you `pip install recurring-ical-events` on the Pi it is used
instead for full RFC 5545 coverage.
"""
import calendar as _cal
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_tz(name):
    """Timezone by name. Windows has no built-in timezone database, so if it's missing
    we fall back to the computer's current UTC offset (fine for testing; run
    `py -m pip install tzdata` for exact daylight-saving handling). The Pi doesn't need this."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        if not getattr(get_tz, "_warned", False):
            print("[time] tip: run 'py -m pip install tzdata' for exact daylight-saving times")
            get_tz._warned = True
        return datetime.now().astimezone().tzinfo

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
MAX_INSTANCES = 2000


def fetch(url, timeout=20):
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    req = urllib.request.Request(url, headers={"User-Agent": "FamilyHub/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- parsing
def _unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _split(line):
    """'DTSTART;TZID=America/New_York:20261006T090000' -> name, params, value"""
    head, _, value = line.partition(":")
    parts = head.split(";")
    params = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def _unescape(s):
    return s.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_dt(value, params, local_tz):
    """Returns (datetime-or-date, all_day)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or (len(value) == 8 and value.isdigit()):
        return datetime.strptime(value[:8], "%Y%m%d").date(), True
    utc = value.endswith("Z")
    dt = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if utc:
        dt = dt.replace(tzinfo=timezone.utc)
    elif "TZID" in params:
        try:
            dt = dt.replace(tzinfo=get_tz(params["TZID"]))
        except Exception:  # Windows-style TZ names from Outlook etc.
            dt = dt.replace(tzinfo=local_tz)
    else:
        dt = dt.replace(tzinfo=local_tz)  # floating time
    return dt.astimezone(local_tz), False


def parse(text, local_tz):
    events = []
    cur = None
    depth_other = 0
    for line in _unfold(text):
        if not line:
            continue
        name, params, value = _split(line)
        if name == "BEGIN":
            if value.upper() == "VEVENT":
                cur = {"exdates": set(), "title": "", "location": "", "rrule": None,
                       "status": "", "recurrence_id": None}
            elif cur is not None:
                depth_other += 1  # e.g. VALARM inside VEVENT
            continue
        if name == "END":
            if value.upper() == "VEVENT" and cur is not None:
                if "start" in cur and cur["status"].upper() != "CANCELLED":
                    events.append(cur)
                cur = None
            elif cur is not None and depth_other:
                depth_other -= 1
            continue
        if cur is None or depth_other:
            continue
        if name == "UID":
            cur["uid"] = value
        elif name == "SUMMARY":
            cur["title"] = _unescape(value)
        elif name == "LOCATION":
            cur["location"] = _unescape(value)
        elif name == "STATUS":
            cur["status"] = value
        elif name == "DTSTART":
            cur["start"], cur["all_day"] = _parse_dt(value, params, local_tz)
        elif name == "DTEND":
            cur["end"], _ = _parse_dt(value, params, local_tz)
        elif name == "DURATION":
            cur["duration"] = _parse_duration(value)
        elif name == "RRULE":
            cur["rrule"] = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
        elif name == "EXDATE":
            for v in value.split(","):
                d, _ = _parse_dt(v, params, local_tz)
                cur["exdates"].add(_key(d))
        elif name == "RECURRENCE-ID":
            cur["recurrence_id"], _ = _parse_dt(value, params, local_tz)
    for e in events:
        if "end" not in e:
            if "duration" in e:
                e["end"] = e["start"] + e["duration"]
            else:
                e["end"] = e["start"] + (timedelta(days=1) if e["all_day"] else timedelta(hours=1))
        e.setdefault("uid", f"{e['title']}-{e['start']}")
    return events


def _parse_duration(v):
    v = v.lstrip("+")
    sign = -1 if v.startswith("-") else 1
    v = v.lstrip("-P")
    days = secs = 0
    num = ""
    in_time = False
    for ch in v:
        if ch == "T":
            in_time = True
        elif ch.isdigit():
            num += ch
        else:
            n = int(num or 0)
            num = ""
            if ch == "W":
                days += 7 * n
            elif ch == "D":
                days += n
            elif ch == "H":
                secs += 3600 * n
            elif ch == "M" and in_time:
                secs += 60 * n
            elif ch == "S":
                secs += n
    return sign * timedelta(days=days, seconds=secs)


def _key(d):
    return d.isoformat()[:16] if isinstance(d, datetime) else d.isoformat()


# ---------------------------------------------------------------- recurrence
def _nth_weekdays(year, month, weekday, ordinal):
    days = [d for d in range(1, _cal.monthrange(year, month)[1] + 1)
            if date(year, month, d).weekday() == weekday]
    if ordinal == 0:
        return days
    try:
        return [days[ordinal - 1] if ordinal > 0 else days[ordinal]]
    except IndexError:
        return []


def _add_months(d, n):
    m = d.month - 1 + n
    return d.replace(year=d.year + m // 12, month=m % 12 + 1, day=1)


def _occurrences(ev, window_end, local_tz):
    """Yield start values (date or datetime) for one recurring master event."""
    rr = ev["rrule"]
    start = ev["start"]
    freq = rr.get("FREQ", "DAILY").upper()
    interval = int(rr.get("INTERVAL", 1))
    count = int(rr["COUNT"]) if "COUNT" in rr else None
    until = None
    if "UNTIL" in rr:
        until, _ = _parse_dt(rr["UNTIL"], {}, local_tz)
        if isinstance(start, datetime) and not isinstance(until, datetime):
            until = datetime.combine(until, datetime.max.time()).replace(tzinfo=local_tz)
        if not isinstance(start, datetime) and isinstance(until, datetime):
            until = until.date()
    byday = []
    for tok in filter(None, rr.get("BYDAY", "").split(",")):
        ordinal = int(tok[:-2]) if len(tok) > 2 else 0
        byday.append((WEEKDAYS.index(tok[-2:].upper()), ordinal))
    bymonthday = [int(x) for x in filter(None, rr.get("BYMONTHDAY", "").split(","))]

    def at(day):
        if isinstance(start, datetime):
            naive = datetime.combine(day, start.astimezone(local_tz).time().replace(tzinfo=None))
            return naive.replace(tzinfo=local_tz)  # keeps wall-clock time across DST
        return day

    start_day = start.date() if isinstance(start, datetime) else start
    end_day = window_end.date() if isinstance(window_end, datetime) else window_end
    produced = 0
    period = 0
    while produced < MAX_INSTANCES:
        if freq == "DAILY":
            days = [start_day + timedelta(days=period * interval)]
        elif freq == "WEEKLY":
            week_start = start_day - timedelta(days=start_day.weekday()) + timedelta(weeks=period * interval)
            wds = sorted({w for w, _ in byday}) or [start_day.weekday()]
            days = [week_start + timedelta(days=w) for w in wds]
        elif freq == "MONTHLY":
            m = _add_months(start_day, period * interval)
            if byday:
                days = sorted(date(m.year, m.month, d) for w, o in byday
                              for d in _nth_weekdays(m.year, m.month, w, o))
            else:
                mdays = bymonthday or [start_day.day]
                last = _cal.monthrange(m.year, m.month)[1]
                days = [date(m.year, m.month, (d if d > 0 else last + d + 1))
                        for d in mdays if abs(d) <= last]
        elif freq == "YEARLY":
            y = start_day.year + period * interval
            try:
                days = [start_day.replace(year=y)]
            except ValueError:  # Feb 29
                days = []
        else:
            return
        if days and min(days) > end_day:
            return
        for d in days:
            if d < start_day:
                continue
            occ = at(d)
            if until is not None and occ > until:
                return
            if count is not None and produced >= count:
                return
            produced += 1
            yield occ
        period += 1


def expand(events, window_start, window_end, local_tz):
    """Return flat list of instances overlapping [window_start, window_end)."""
    overrides = {}
    for e in events:
        if e.get("recurrence_id") is not None:
            overrides[(e["uid"], _key(e["recurrence_id"]))] = e

    out = []

    def emit(e, s, en):
        out.append({"uid": e["uid"], "title": e["title"] or "(busy)", "location": e["location"],
                    "all_day": e["all_day"], "start": s.isoformat(), "end": en.isoformat()})

    def overlaps(s, en):
        s_cmp = s if isinstance(s, datetime) else datetime.combine(s, datetime.min.time()).replace(tzinfo=local_tz)
        e_cmp = en if isinstance(en, datetime) else datetime.combine(en, datetime.min.time()).replace(tzinfo=local_tz)
        return s_cmp < window_end and e_cmp > window_start

    for e in events:
        if e.get("recurrence_id") is not None:
            if overlaps(e["start"], e["end"]):
                emit(e, e["start"], e["end"])
            continue
        dur = e["end"] - e["start"]
        if not e["rrule"]:
            if overlaps(e["start"], e["end"]):
                emit(e, e["start"], e["end"])
            continue
        for s in _occurrences(e, window_end, local_tz):
            k = _key(s)
            if k in e["exdates"] or (e["uid"], k) in overrides:
                continue
            if overlaps(s, s + dur):
                emit(e, s, s + dur)
    return out


def load(url_or_text, days_back=7, days_ahead=90, tz_name="America/New_York"):
    local_tz = get_tz(tz_name)
    text = url_or_text if url_or_text.lstrip().startswith("BEGIN:VCALENDAR") else fetch(url_or_text)
    now = datetime.now(local_tz)
    w_start = (now - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    w_end = now + timedelta(days=days_ahead)
    try:  # Prefer the full library when it's installed on the Pi.
        import icalendar, recurring_ical_events  # noqa: E401
        cal = icalendar.Calendar.from_ical(text)
        out = []
        for c in recurring_ical_events.of(cal).between(w_start, w_end):
            s, en = c.decoded("DTSTART"), c.decoded("DTEND", None) or c.decoded("DTSTART")
            all_day = not isinstance(s, datetime)
            if not all_day:
                s, en = s.astimezone(local_tz), en.astimezone(local_tz)
            out.append({"uid": str(c.get("UID", "")), "title": str(c.get("SUMMARY", "(busy)")),
                        "location": str(c.get("LOCATION", "")), "all_day": all_day,
                        "start": s.isoformat(), "end": en.isoformat()})
        return out
    except ImportError:
        return expand(parse(text, local_tz), w_start, w_end, local_tz)

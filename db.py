"""SQLite storage for FamilyHub. Standard library only."""
import json
import sqlite3
import threading
from datetime import datetime, date, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#4F7CAC',
    emoji TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS calendars (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ics_url TEXT NOT NULL,
    member_id INTEGER REFERENCES members(id),
    last_synced TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    calendar_id INTEGER REFERENCES calendars(id) ON DELETE CASCADE,
    member_id INTEGER REFERENCES members(id),
    uid TEXT,
    title TEXT NOT NULL,
    location TEXT DEFAULT '',
    start TEXT NOT NULL,      -- ISO local datetime, or YYYY-MM-DD for all-day
    end TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'local'   -- 'local' or 'ics'
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start);
CREATE TABLE IF NOT EXISTS chores (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    member_id INTEGER REFERENCES members(id),
    repeat TEXT NOT NULL DEFAULT 'daily',  -- daily | weekly:MO,WE | once
    points INTEGER NOT NULL DEFAULT 1,
    due_date TEXT                          -- for 'once' chores
);
CREATE TABLE IF NOT EXISTS chore_done (
    chore_id INTEGER REFERENCES chores(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    done_at TEXT NOT NULL,
    PRIMARY KEY (chore_id, day)
);
CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS list_items (
    id INTEGER PRIMARY KEY,
    list_id INTEGER REFERENCES lists(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    done_at TEXT
);
-- Every interaction is logged so the suggestion engine can learn routines.
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS dismissed (
    key TEXT PRIMARY KEY,
    at TEXT NOT NULL
);
"""

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


class DB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        # Events that came from a calendar link which no longer exists (like the demo
        # week) can't be re-synced, so they belong to the hub now and are editable.
        self.conn.execute("UPDATE events SET source='local' WHERE source='ics' AND calendar_id IS NULL")
        self.conn.commit()
        self.lock = threading.Lock()

    # ---- helpers -------------------------------------------------------
    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def log(self, kind, **payload):
        self.x("INSERT INTO activity(kind, payload, at) VALUES (?,?,?)",
               (kind, json.dumps(payload), datetime.now().isoformat(timespec="seconds")))

    # ---- members -------------------------------------------------------
    def members(self):
        return self.q("SELECT * FROM members ORDER BY id")

    def add_member(self, name, color, emoji=""):
        return self.x("INSERT INTO members(name,color,emoji) VALUES (?,?,?)", (name.strip(), color, emoji))

    def update_member(self, member_id, name, color, emoji=""):
        self.x("UPDATE members SET name=?, color=?, emoji=? WHERE id=?", (name.strip(), color, emoji, member_id))

    def delete_member(self, member_id):
        """Removes a person. Their events, chores and calendars stay, just unassigned."""
        with self.lock:
            for table in ("events", "chores", "calendars"):
                self.conn.execute(f"UPDATE {table} SET member_id=NULL WHERE member_id=?", (member_id,))
            self.conn.execute("DELETE FROM members WHERE id=?", (member_id,))
            self.conn.commit()

    # ---- meta (small saved flags) -------------------------------------
    def get_meta(self, key):
        rows = self.q("SELECT value FROM meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    def set_meta(self, key, value):
        self.x("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", (key, value))

    # ---- events --------------------------------------------------------
    def events_between(self, start, end):
        """start/end are YYYY-MM-DD strings; end exclusive."""
        return self.q(
            """SELECT e.*, m.name AS member, m.color AS color
               FROM events e LEFT JOIN members m ON m.id = e.member_id
               WHERE e.start < ? AND e.end > ? ORDER BY e.all_day DESC, e.start""",
            (end, start))

    def add_event(self, title, start, end, all_day=False, member_id=None, location=""):
        eid = self.x(
            "INSERT INTO events(title,start,end,all_day,member_id,location,source) VALUES (?,?,?,?,?,?, 'local')",
            (title, start, end, int(all_day), member_id, location))
        self.log("event_added", title=title, start=start, member_id=member_id)
        return eid

    def update_event(self, eid, title, start, end, all_day=False, member_id=None, location=""):
        self.x("""UPDATE events SET title=?, start=?, end=?, all_day=?, member_id=?, location=?
                  WHERE id=? AND source='local'""",
               (title, start, end, int(all_day), member_id, location, eid))

    def delete_event(self, eid):
        self.x("DELETE FROM events WHERE id=? AND source='local'", (eid,))

    def replace_calendar_events(self, calendar_id, member_id, events):
        with self.lock:
            self.conn.execute("DELETE FROM events WHERE calendar_id=?", (calendar_id,))
            self.conn.executemany(
                """INSERT INTO events(calendar_id,member_id,uid,title,location,start,end,all_day,source)
                   VALUES (?,?,?,?,?,?,?,?,'ics')""",
                [(calendar_id, member_id, e["uid"], e["title"], e["location"],
                  e["start"], e["end"], int(e["all_day"])) for e in events])
            self.conn.execute("UPDATE calendars SET last_synced=? WHERE id=?",
                              (datetime.now().isoformat(timespec="seconds"), calendar_id))
            self.conn.commit()

    # ---- chores --------------------------------------------------------
    def chores_for(self, day: date):
        code = WEEKDAYS[day.weekday()]
        out = []
        rows = self.q("""SELECT c.*, m.name AS member, m.color AS color
                         FROM chores c LEFT JOIN members m ON m.id=c.member_id ORDER BY c.member_id, c.id""")
        done = {r["chore_id"] for r in self.q("SELECT chore_id FROM chore_done WHERE day=?", (day.isoformat(),))}
        for c in rows:
            r = c["repeat"]
            applies = (r == "daily"
                       or (r.startswith("weekly:") and code in r[7:].split(","))
                       or (r == "once" and c["due_date"] == day.isoformat()))
            if applies:
                c["done"] = c["id"] in done
                out.append(c)
        return out

    def add_chore(self, title, member_id, repeat="daily", points=1, due_date=None):
        return self.x("INSERT INTO chores(title,member_id,repeat,points,due_date) VALUES (?,?,?,?,?)",
                      (title, member_id, repeat, points, due_date))

    def toggle_chore(self, chore_id, day):
        existing = self.q("SELECT 1 FROM chore_done WHERE chore_id=? AND day=?", (chore_id, day))
        if existing:
            self.x("DELETE FROM chore_done WHERE chore_id=? AND day=?", (chore_id, day))
            return False
        self.x("INSERT INTO chore_done(chore_id,day,done_at) VALUES (?,?,?)",
               (chore_id, day, datetime.now().isoformat(timespec="seconds")))
        self.log("chore_done", chore_id=chore_id, day=day)
        return True

    def points_this_week(self):
        monday = date.today() - timedelta(days=date.today().weekday())
        return self.q("""SELECT m.id, m.name, m.color,
                         (SELECT COALESCE(SUM(c.points),0) FROM chore_done d JOIN chores c ON c.id=d.chore_id
                          WHERE c.member_id=m.id AND d.day >= ?) AS points
                      FROM members m ORDER BY m.id""", (monday.isoformat(),))

    # ---- lists ---------------------------------------------------------
    def lists(self):
        out = []
        for l in self.q("SELECT * FROM lists ORDER BY id"):
            l["items"] = self.q("SELECT * FROM list_items WHERE list_id=? ORDER BY done, id", (l["id"],))
            out.append(l)
        return out

    def ensure_list(self, name):
        rows = self.q("SELECT id FROM lists WHERE name=?", (name,))
        return rows[0]["id"] if rows else self.x("INSERT INTO lists(name) VALUES (?)", (name,))

    def add_item(self, list_id, text):
        iid = self.x("INSERT INTO list_items(list_id,text,added_at) VALUES (?,?,?)",
                     (list_id, text.strip(), datetime.now().isoformat(timespec="seconds")))
        self.log("item_added", list_id=list_id, text=text.strip().lower())
        return iid

    def toggle_item(self, item_id):
        row = self.q("SELECT done, text, list_id FROM list_items WHERE id=?", (item_id,))
        if not row:
            return None
        new = 0 if row[0]["done"] else 1
        self.x("UPDATE list_items SET done=?, done_at=? WHERE id=?",
               (new, datetime.now().isoformat(timespec="seconds") if new else None, item_id))
        if new:
            self.log("item_done", list_id=row[0]["list_id"], text=row[0]["text"].lower())
        return bool(new)

    def clear_done(self, list_id):
        self.x("DELETE FROM list_items WHERE list_id=? AND done=1", (list_id,))

    # ---- suggestions bookkeeping --------------------------------------
    def dismiss(self, key):
        self.x("INSERT OR REPLACE INTO dismissed(key,at) VALUES (?,?)",
               (key, datetime.now().isoformat(timespec="seconds")))

    def dismissed_keys(self):
        return {r["key"] for r in self.q("SELECT key FROM dismissed")}

    def activity(self, kind, since_days=120):
        since = (datetime.now() - timedelta(days=since_days)).isoformat()
        rows = self.q("SELECT payload, at FROM activity WHERE kind=? AND at>=? ORDER BY at", (kind, since))
        for r in rows:
            r.update(json.loads(r.pop("payload")))
        return rows

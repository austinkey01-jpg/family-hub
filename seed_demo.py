#!/usr/bin/env python3
"""Fill FamilyHub with a believable demo week so you can see everything working.

    python3 seed_demo.py      # then: python3 server.py
Delete data/familyhub.db to start fresh.
"""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import ics
from db import DB

ROOT = Path(__file__).parent
cfg_path = ROOT / "config.json" if (ROOT / "config.json").exists() else ROOT / "config.example.json"
CFG = json.loads(cfg_path.read_text(encoding="utf-8"))
db = DB(ROOT / "data" / "familyhub.db")

if not db.members():
    for m in CFG["members"]:
        db.add_member(m["name"], m["color"], m.get("emoji", ""))
db.set_meta("members_seeded", "1")
M = {m["name"]: m["id"] for m in db.members()}
names = list(M)
dad, mom, kid1, kid2 = (names + names)[:4]

today = date.today()
monday = today - timedelta(days=today.weekday())
fmt = lambda d: d.strftime("%Y%m%d")

# A small iCal feed, the same format Google/iCloud/Outlook publish, to exercise the parser.
DEMO_ICS = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:soccer-1
SUMMARY:{kid2} soccer practice
DTSTART;TZID=America/New_York:{fmt(monday)}T173000
DTEND;TZID=America/New_York:{fmt(monday)}T183000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE
LOCATION:Riverside Park
END:VEVENT
BEGIN:VEVENT
UID:piano-1
SUMMARY:{kid1} piano lesson
DTSTART;TZID=America/New_York:{fmt(monday)}T160000
DTEND;TZID=America/New_York:{fmt(monday)}T164500
RRULE:FREQ=WEEKLY;BYDAY=TU,TH
END:VEVENT
BEGIN:VEVENT
UID:trash-1
SUMMARY:Trash & recycling night
DTSTART;VALUE=DATE:{fmt(monday + timedelta(days=3))}
DTEND;VALUE=DATE:{fmt(monday + timedelta(days=4))}
RRULE:FREQ=WEEKLY
END:VEVENT
BEGIN:VEVENT
UID:game-1
SUMMARY:{kid2} soccer game
DTSTART;TZID=America/New_York:{fmt(monday + timedelta(days=5))}T090000
DTEND;TZID=America/New_York:{fmt(monday + timedelta(days=5))}T103000
LOCATION:Lincoln Fields
END:VEVENT
END:VCALENDAR
"""
cal_id = db.x("INSERT INTO calendars(name, ics_url, member_id) VALUES (?,?,?)", ("Demo kids calendar", "demo", None))
evs = ics.load(DEMO_ICS, tz_name=CFG.get("timezone", "America/New_York"))
for e in evs:  # attach each event to the kid named in its title
    e["member_id"] = next((M[n] for n in M if e["title"].startswith(n)), None)
with db.lock:
    db.conn.execute("DELETE FROM events WHERE calendar_id=?", (cal_id,))
    db.conn.executemany(
        "INSERT INTO events(calendar_id,member_id,uid,title,location,start,end,all_day,source) VALUES (?,?,?,?,?,?,?,?,'ics')",
        [(cal_id, e["member_id"], e["uid"], e["title"], e["location"], e["start"], e["end"], int(e["all_day"])) for e in evs])
    db.conn.commit()
# The demo feed was loaded from text, so remove its placeholder row (the sync loop
# would otherwise try to fetch "demo" as a URL). Its events stay.
db.x("UPDATE events SET calendar_id=NULL WHERE calendar_id=?", (cal_id,))
db.x("DELETE FROM calendars WHERE id=?", (cal_id,))

# Local events, including a deliberate double-booking for the conflict detector.
d = lambda n, t: f"{(monday + timedelta(days=n)).isoformat()}T{t}"
db.add_event(f"{dad} dentist", d(2, "08:30"), d(2, "09:30"), member_id=M[dad])
db.add_event("Date night 🍝", d(4, "19:00"), d(4, "21:30"), member_id=M[mom])
db.add_event(f"{mom} work offsite", d(1, "09:00"), d(1, "15:00"), member_id=M[mom])
db.add_event(f"{mom} parent-teacher conference", d(1, "14:00"), d(1, "14:30"), member_id=M[mom])
db.add_event("Grandma's birthday party", d(6, "13:00"), d(6, "16:00"))

# Chores
for title, who, rep, pts in [
    ("Make bed", kid2, "daily", 1), ("Feed the dog", kid2, "daily", 2),
    ("Empty dishwasher", kid1, "daily", 2), ("Take out trash", kid1, "weekly:TH", 3),
    ("Laundry", mom, "weekly:MO,TH", 2), ("Mow the lawn", dad, "weekly:SA", 3),
]:
    db.add_chore(title, M[who], rep, pts)
for c in db.chores_for(today - timedelta(days=1))[:3]:
    db.toggle_chore(c["id"], (today - timedelta(days=1)).isoformat())

# Lists + 3 months of grocery history so restock predictions have something to learn from.
gid = db.ensure_list("Groceries")
for name in CFG.get("lists", []):
    db.ensure_list(name)
history = {"milk": 6, "eggs": 9, "bananas": 5, "coffee": 14, "bread": 7}
random.seed(4)
for item, every in history.items():
    day = today - timedelta(days=90)
    while day < today - timedelta(days=every - 1):
        db.x("INSERT INTO activity(kind,payload,at) VALUES ('item_added',?,?)",
             (json.dumps({"list_id": gid, "text": item}), datetime.combine(day, datetime.min.time()).isoformat()))
        day += timedelta(days=every + random.choice([-1, 0, 0, 1]))
for t in ["Apples", "Pasta", "Paper towels"]:
    db.add_item(gid, t)
todo = db.ensure_list("To-Do")
for t in ["Schedule car inspection", "RSVP to Grandma's party", "Return library books"]:
    db.add_item(todo, t)

print(f"Seeded {len(evs)} calendar instances, events, chores and lists into data/familyhub.db")

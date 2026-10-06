"""Smart suggestions: on-device pattern learning, no cloud needed.

Each suggestion has a stable `key` so the family can dismiss it and it stays gone.
Rules:
  1. Schedule conflicts      - same person double-booked
  2. Busy-day heads-up       - lots going on tomorrow
  3. Prep reminders          - "Soccer game" tomorrow -> pack the gear
  4. Restock predictions     - learns how often you buy milk, suggests adding it
  5. Chore nudges            - chores missed yesterday, weekly points leader
"""
import re
import statistics
from datetime import date, datetime, timedelta

PREP_RULES = [
    (r"\b(soccer|football|baseball|softball|lacrosse|hockey)\b", "Pack {sport} gear and a water bottle", "⚽"),
    (r"\b(swim|swimming)\b", "Pack a towel and goggles", "🏊"),
    (r"\b(dentist|doctor|dr\.?|pediatric|appointment|checkup)\b", "Bring insurance card", "🩺"),
    (r"\b(birthday|bday)\b.*\bparty\b|\bparty\b.*\b(birthday|bday)\b", "Get a gift and a card", "🎁"),
    (r"\b(field trip)\b", "Sign the permission slip, pack a lunch", "🚌"),
    (r"\b(game|match|tournament)\b", "Charge the camera and pack snacks", "🏆"),
    (r"\b(flight|airport)\b", "Check in online and pack chargers", "✈️"),
    (r"\b(recital|concert)\b", "Lay out the outfit tonight", "🎻"),
]


def _clock(dt):
    """'5:30 PM' without a leading zero. (strftime's %-I only works on Linux/Mac.)"""
    return dt.strftime("%I:%M %p").lstrip("0")


def _day(s):
    return s[:10]


def _dt(s):
    if len(s) == 10:
        return datetime.fromisoformat(s)
    return datetime.fromisoformat(s).replace(tzinfo=None)


def conflicts(db, today):
    out = []
    end = (today + timedelta(days=7)).isoformat()
    evs = [e for e in db.events_between(today.isoformat(), end) if not e["all_day"] and e["member_id"]]
    by_member = {}
    for e in evs:
        by_member.setdefault(e["member_id"], []).append(e)
    for mid, lst in by_member.items():
        lst.sort(key=lambda e: _dt(e["start"]))
        for a, b in zip(lst, lst[1:]):
            if _dt(b["start"]) < _dt(a["end"]):
                when = _dt(b["start"]).strftime("%a ") + _clock(_dt(b["start"]))
                out.append({
                    "key": f"conflict:{a['id']}:{b['id']}",
                    "kind": "conflict", "icon": "⚠️", "priority": 0,
                    "title": f"{a['member']} is double-booked {when}",
                    "detail": f"“{a['title']}” overlaps “{b['title']}”.",
                })
    return out


def busy_day(db, today):
    tmr = today + timedelta(days=1)
    evs = [e for e in db.events_between(tmr.isoformat(), (tmr + timedelta(days=1)).isoformat()) if not e["all_day"]]
    if len(evs) >= 4:
        first = min(evs, key=lambda e: e["start"])
        return [{
            "key": f"busy:{tmr}", "kind": "busy", "icon": "📅", "priority": 2,
            "title": f"Big day tomorrow: {len(evs)} things on the calendar",
            "detail": f"First up is “{first['title']}” at {_clock(_dt(first['start']))}. "
                      "Maybe set out bags and lunches tonight.",
        }]
    return []


def prep(db, today):
    out = []
    tmr = today + timedelta(days=1)
    for e in db.events_between(today.isoformat(), (tmr + timedelta(days=1)).isoformat()):
        title = e["title"].lower()
        for pattern, tip, icon in PREP_RULES:
            m = re.search(pattern, title)
            if m:
                when = "today" if _day(e["start"]) == today.isoformat() else "tomorrow"
                who = f"{e['member']}'s " if e.get("member") and not e["title"].startswith(e["member"]) else ""
                out.append({
                    "key": f"prep:{e['id']}:{pattern[:12]}", "kind": "prep", "icon": icon, "priority": 1,
                    "title": f"{who}{e['title']} {when}",
                    "detail": tip.format(sport=m.group(1) if m.groups() else ""),
                })
                break
    return out


def restock(db, today):
    """Learns purchase cadence from the grocery list history.
    Items you add at least 3 times get a typical interval; once that's passed and the
    item isn't already on a list, it's suggested. Bundled into one card."""
    adds = db.activity("item_added", since_days=180)
    history = {}
    for a in adds:
        history.setdefault(a["text"], []).append(datetime.fromisoformat(a["at"]).date())
    on_lists = {i["text"].lower() for l in db.lists() for i in l["items"] if not i["done"]}
    grocery_id = db.ensure_list("Groceries")
    due_items = []
    for item, days in history.items():
        days = sorted(set(days))
        if len(days) < 3 or item in on_lists:
            continue
        cadence = statistics.median((b - a).days for a, b in zip(days, days[1:]))
        if cadence >= 2 and days[-1] + timedelta(days=round(cadence)) <= today:
            overdue = (today - days[-1]).days / cadence
            due_items.append((overdue, item, round(cadence)))
    if not due_items:
        return []
    due_items.sort(reverse=True)
    names = [i for _, i, _ in due_items]
    top = due_items[0]
    detail = (f"You usually buy {top[1]} every {top[2]} days." if len(names) == 1 else
              f"Based on how often you buy them (e.g. {top[1]} about every {top[2]} days).")
    return [{
        "key": f"restock:{','.join(sorted(names))}:{today}", "kind": "restock", "icon": "🛒", "priority": 2,
        "title": "Probably time to restock " + (names[0] if len(names) == 1 else
                                                 ", ".join(names[:-1]) + " and " + names[-1]),
        "detail": detail,
        "action": {"type": "add_items", "list_id": grocery_id, "items": names,
                   "label": "Add to Groceries" if len(names) == 1 else f"Add all {len(names)}"},
    }]


def chores(db, today):
    out = []
    yday = today - timedelta(days=1)
    missed = [c for c in db.chores_for(yday) if not c["done"] and c["repeat"] != "once"]
    by_member = {}
    for c in missed:
        by_member.setdefault(c["member"] or "Someone", []).append(c["title"])
    for who, items in by_member.items():
        out.append({
            "key": f"missed:{who}:{yday}", "kind": "chore", "icon": "🧹", "priority": 3,
            "title": f"{who} missed {len(items)} chore{'s' if len(items) > 1 else ''} yesterday",
            "detail": ", ".join(items[:4]),
        })
    pts = [p for p in db.points_this_week() if p["points"]]
    pts.sort(key=lambda p: -p["points"])
    if pts and (len(pts) == 1 or pts[0]["points"] > pts[1]["points"]):
        leader = pts[0]
        out.append({
            "key": f"leader:{leader['name']}:{today}", "kind": "chore", "icon": "⭐", "priority": 4,
            "title": f"{leader['name']} is leading the week with {leader['points']} points",
            "detail": "Keep it up!",
        })
    return out


def all_suggestions(db, today=None):
    today = today or date.today()
    found = []
    for rule in (conflicts, prep, busy_day, restock, chores):
        try:
            found += rule(db, today)
        except Exception as exc:  # one bad rule shouldn't blank the panel
            print(f"[suggestions] {rule.__name__} failed: {exc}")
    gone = db.dismissed_keys()
    found = [s for s in found if s["key"] not in gone]
    return sorted(found, key=lambda s: s["priority"])

#!/usr/bin/env python3
"""FamilyHub server: serves the touchscreen UI and a small JSON API.

Run:  python3 server.py            (then open http://localhost:8080)
Standard library only; optional extras are listed in README.md.
"""
import json
import re
import threading
import time
import traceback
import urllib.request
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import ics
import suggestions
from ai import AI
from db import DB
from voice import Voice

ROOT = Path(__file__).parent
CFG_PATH = ROOT / "config.json"
if not CFG_PATH.exists():
    CFG_PATH = ROOT / "config.example.json"
CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))

db = DB(ROOT / "data" / "familyhub.db")
ai = AI(CFG)
voice = Voice(CFG, ROOT / "data" / "tts_cache")
_weather = {"at": 0, "data": None}


# ------------------------------------------------------------------ setup
def seed_from_config():
    # Starter family from config, first run only. After that the Family screen is in charge
    # (so deleting everyone in the app doesn't bring the starter people back).
    if not db.get_meta("members_seeded"):
        if not db.members():
            for m in CFG.get("members", []):
                db.add_member(m["name"], m.get("color", "#4F7CAC"), m.get("emoji", ""))
        db.set_meta("members_seeded", "1")
    names = {m["name"]: m["id"] for m in db.members()}
    existing = {c["ics_url"] for c in db.q("SELECT ics_url FROM calendars")}
    for c in CFG.get("calendars", []):
        if c["url"] and c["url"] not in existing:
            db.x("INSERT INTO calendars(name, ics_url, member_id) VALUES (?,?,?)",
                 (c["name"], c["url"], names.get(c.get("member"))))
    for name in CFG.get("lists", ["Groceries", "To-Do"]):
        db.ensure_list(name)


def sync_calendars():
    for cal in db.q("SELECT * FROM calendars"):
        try:
            evs = ics.load(cal["ics_url"], tz_name=CFG.get("timezone", "America/New_York"))
            db.replace_calendar_events(cal["id"], cal["member_id"], evs)
            print(f"[sync] {cal['name']}: {len(evs)} events")
        except Exception as exc:
            print(f"[sync] {cal['name']} failed: {exc}")


def sync_loop():
    while True:
        sync_calendars()
        time.sleep(60 * int(CFG.get("sync_minutes", 10)))


def weather():
    """Never blocks a page load: returns the cached forecast and refreshes it in the background."""
    loc = CFG.get("location") or {}
    if "lat" in loc and time.time() - _weather["at"] > 1800:
        _weather["at"] = time.time()  # also rate-limits retries when offline
        threading.Thread(target=_fetch_weather, args=(loc,), daemon=True).start()
    return _weather["data"]


def _fetch_weather(loc):
    unit = "fahrenheit" if CFG.get("units", "imperial") == "imperial" else "celsius"
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={loc['lat']}&longitude={loc['lon']}"
           f"&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code"
           f"&temperature_unit={unit}&timezone=auto&forecast_days=5")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            _weather["data"] = json.loads(r.read())
    except Exception as exc:
        _weather["at"] = time.time() - 1500  # retry in ~5 min
        print(f"[weather] {exc}")


# ------------------------------------------------------------------ http
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web"), **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            return  # keep the journal quiet
        super().log_message(fmt, *args)

    def _json(self, obj, code=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/"):
            return super().do_GET()
        try:
            self._route("GET", u.path, parse_qs(u.query))
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        try:
            self._route("POST", urlparse(self.path).path, {})
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": str(exc)}, 500)

    def do_DELETE(self):
        try:
            self._route("DELETE", urlparse(self.path).path, {})
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _route(self, method, path, qs):
        today = date.today()
        m = re.match(r"^/api/(\w[\w-]*)(?:/(\d+))?(?:/(\w+))?$", path)
        if not m:
            return self._json({"error": "not found"}, 404)
        res, rid, action = m.group(1), m.group(2), m.group(3)
        rid = int(rid) if rid else None

        if method == "GET" and res == "state":
            start = qs.get("start", [today.isoformat()])[0]
            days = int(qs.get("days", ["7"])[0])
            end = (date.fromisoformat(start) + timedelta(days=days)).isoformat()
            return self._json({
                "family_name": CFG.get("family_name", "Our Family"),
                "members": db.members(),
                "events": db.events_between(start, end),
                "chores": db.chores_for(today),
                "points": db.points_this_week(),
                "lists": db.lists(),
                "suggestions": suggestions.all_suggestions(db),
                "weather": weather(),
                "features": {"ai": ai.enabled, "voice": voice.enabled},
                "today": today.isoformat(),
            })

        if res == "members":
            if method == "POST":
                b = self._body()
                name = (b.get("name") or "").strip()
                if not name:
                    return self._json({"error": "Every family member needs a name."}, 400)
                color, emoji = b.get("color") or "#3B6EA8", b.get("emoji") or ""
                if rid:
                    db.update_member(rid, name, color, emoji)
                    return self._json({"id": rid})
                return self._json({"id": db.add_member(name, color, emoji)})
            if method == "DELETE" and rid:
                db.delete_member(rid)
                return self._json({"ok": True})

        if res == "events":
            if method == "POST" and rid:
                b = self._body()
                db.update_event(rid, b["title"], b["start"], b.get("end") or b["start"],
                                b.get("all_day", False), b.get("member_id"), b.get("location", ""))
                return self._json({"id": rid})
            if method == "POST":
                b = self._body()
                return self._json({"id": db.add_event(b["title"], b["start"], b.get("end") or b["start"],
                                                      b.get("all_day", False), b.get("member_id"),
                                                      b.get("location", ""))})
            if method == "DELETE" and rid:
                db.delete_event(rid)
                return self._json({"ok": True})

        if res == "chores":
            if method == "POST" and rid and action == "toggle":
                day = self._body().get("day", today.isoformat())
                return self._json({"done": db.toggle_chore(rid, day)})
            if method == "POST" and not rid:
                b = self._body()
                return self._json({"id": db.add_chore(b["title"], b.get("member_id"), b.get("repeat", "daily"),
                                                      int(b.get("points", 1)), b.get("due_date"))})
            if method == "DELETE" and rid:
                db.x("DELETE FROM chores WHERE id=?", (rid,))
                return self._json({"ok": True})

        if res == "lists" and method == "POST":
            if rid and action == "items":
                return self._json({"id": db.add_item(rid, self._body()["text"])})
            if rid and action == "clear":
                db.clear_done(rid)
                return self._json({"ok": True})

        if res == "items" and method == "POST" and rid and action == "toggle":
            return self._json({"done": db.toggle_item(rid)})

        if res == "suggestions" and method == "POST" and action is None and rid is None:
            db.dismiss(self._body()["key"])
            return self._json({"ok": True})

        if res == "quick-add" and method == "POST":
            if not ai.enabled:
                return self._json({"error": "Add an Anthropic API key in config.json to use quick add."}, 400)
            ev = ai.quick_add(self._body()["text"], db.members())
            ev["id"] = db.add_event(ev["title"], ev["start"], ev["end"], ev.get("all_day", False),
                                    ev.get("member_id"), ev.get("location", ""))
            return self._json(ev)

        if res == "brief" and method == "GET":
            if not ai.enabled:
                return self._json({"text": None})
            return self._json({"text": ai.daily_brief(db, suggestions.all_suggestions(db))})

        if res == "speak" and method == "POST":
            wav = voice.synth(self._body()["text"])
            data = wav.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if res == "sync" and method == "POST":
            threading.Thread(target=sync_calendars, daemon=True).start()
            return self._json({"ok": True})

        return self._json({"error": "not found"}, 404)


def main():
    seed_from_config()
    threading.Thread(target=sync_loop, daemon=True).start()
    port = int(CFG.get("port", 8080))
    print(f"FamilyHub on http://localhost:{port}  (config: {CFG_PATH.name})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

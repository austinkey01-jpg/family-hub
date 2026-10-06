"""Cloud AI features (the "hybrid" half). Uses the Claude API over plain HTTPS.

Everything here is optional: if no API key is configured, the app still works and
these features simply hide themselves.

Features:
  * daily_brief  - a warm 2-3 sentence morning summary (spoken in Dad's voice later)
  * quick_add    - "Emma soccer Thursday 5:30 at Riverside" -> structured event
"""
import json
import urllib.request
from datetime import date, datetime, timedelta

API_URL = "https://api.anthropic.com/v1/messages"


class AI:
    def __init__(self, cfg):
        self.key = (cfg.get("anthropic_api_key") or "").strip()
        self.model = cfg.get("ai_model", "claude-haiku-4-5-20251001")
        self.tz = cfg.get("timezone", "America/New_York")
        self.family_name = cfg.get("family_name", "the family")
        self._brief_cache = {}

    @property
    def enabled(self):
        return bool(self.key)

    def _ask(self, system, user, max_tokens=400):
        body = json.dumps({
            "model": self.model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data.get("content", []))

    # ------------------------------------------------------------------
    def daily_brief(self, db, suggestions):
        today = date.today()
        if today in self._brief_cache:
            return self._brief_cache[today]
        events = db.events_between(today.isoformat(), (today + timedelta(days=1)).isoformat())
        chores = db.chores_for(today)
        lines = [f"- {e['start'][11:16] or 'all day'} {e['title']} ({e.get('member') or 'family'})" for e in events]
        chore_lines = [f"- {c['member']}: {c['title']}" for c in chores]
        tips = [f"- {s['title']}: {s['detail']}" for s in suggestions[:5]]
        prompt = (f"Today is {today.strftime('%A, %B')} {today.day}.\nEvents:\n" + ("\n".join(lines) or "- none") +
                  "\nChores:\n" + ("\n".join(chore_lines) or "- none") +
                  "\nHeads-ups:\n" + ("\n".join(tips) or "- none"))
        system = (f"You write the morning message on {self.family_name}'s kitchen wall display. "
                  "It will be read aloud in Dad's voice, so write how a warm, upbeat dad talks: "
                  "2-3 short sentences, plain words, no lists, no emoji, no markdown. "
                  "Mention the most important thing first.")
        text = self._ask(system, prompt, 200).strip()
        self._brief_cache = {today: text}
        return text

    def quick_add(self, text, members):
        now = datetime.now()
        names = ", ".join(f"{m['name']} (id {m['id']})" for m in members)
        system = (
            "Convert a family calendar request into JSON. Reply with JSON only, no prose. "
            'Schema: {"title": str, "start": "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD", '
            '"end": same format, "all_day": bool, "member_ids": [int], "location": str}. '
            "Default duration 1 hour. Resolve relative dates against the current date given. "
            f"Family members: {names}. List every member clearly mentioned in member_ids; empty list if none.")
        user = f"Now: {now.strftime('%A %Y-%m-%d %H:%M')}. Request: {text}"
        raw = self._ask(system, user, 300).strip()
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        ev = json.loads(raw)
        if not ev.get("title") or not ev.get("start"):
            raise ValueError("Couldn't understand that one, try adding a day and time.")
        ev.setdefault("end", ev["start"])
        return ev

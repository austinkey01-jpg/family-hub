# FamilyHub

A Skylight-style family calendar for a Raspberry Pi 5 and a touchscreen, with smart
suggestions and (soon) Dad's voice.

**What works today**
- Week and schedule views, color-coded per person, tap a face to hide/show their stuff
- **Family screen** (⚙ at the top): add, rename, recolor or remove people right on the touchscreen
- Syncs Google, iCloud and Outlook calendars (every 10 min) plus events added on the screen
- Chores per person with points and a weekly leader
- Shared lists (Groceries, To-Do, Meal Ideas…)
- Weather (free, no key) and a night mode after 9 pm
- **Smart suggestions, learned on-device:** double-booking alerts, "pack the cleats"
  prep reminders, busy-day heads-ups, missed-chore nudges, and grocery restock
  predictions learned from how often you buy things
- **Cloud AI (optional, Claude API):** a warm morning message and natural-language
  quick-add ("Emma soccer Thursday 5:30 at Riverside")
- **Dad's voice (Piper, on the Pi):** reads the morning message aloud once his model is trained

The core is plain Python 3 standard library + vanilla JS. No build step, nothing to
compile, easy to modify on the Pi itself.

---

## Try it on your computer first (2 minutes)

You only need Python. In PowerShell, run these one at a time:

```powershell
cd $HOME\OneDrive\Desktop\family-hub
```
```powershell
py seed_demo.py
```
```powershell
py server.py
```
Then open **http://localhost:8080** in your browser. Press Ctrl+C in PowerShell to stop it.

- `seed_demo.py` fills in a pretend week so there's something to look at. Skip it to start empty.
- To wipe everything and start over, stop the server and delete the `data` folder.
- If Windows Firewall asks about Python, click Allow (private networks). That lets your phone open the hub at `http://<your-computer's-IP>:8080`.
- Optional: `py -m pip install tzdata` gives exact daylight-saving times on Windows. The Pi doesn't need it.

On a Mac or Linux, use `python3` instead of `py`.

---

## Parts list

| Part | Notes |
|---|---|
| **Raspberry Pi 5, 4 GB** | 4 GB is plenty for the hybrid setup. 8 GB only if you later want a local LLM. |
| **Raspberry Pi Touch Display 2, 10.1"** | Official panel, 1200×1920, 10-point touch, $80 list. Pi 5 only. Powered from the GPIO header, one ribbon cable, no drivers. |
| Official 27 W USB-C power supply | Pi 5 + screen need the full 5 A. |
| Pi 5 Active Cooler | Required inside a closed shell. |
| NVMe HAT + small SSD (or a good A2 microSD, 32 GB+) | SSD is far more reliable for a 24/7 device. |
| **USB speaker or I2S amp + speaker** | The Pi 5 has no headphone jack. Needed for Dad's voice. |
| Pi 5 RTC battery (optional) | Keeps the clock right through power cuts with no internet. |
| PETG filament | PETG over PLA: the back of a display + Pi gets warm. |
| M2.5 heat-set inserts + screws, French-cleat or VESA mount | |

Check current prices at an approved Raspberry Pi reseller; memory prices have moved a lot this year.

Want something bigger, like a 15"? Use any HDMI + USB-touch portable monitor; the app
scales automatically. The trade-off is an extra cable and a thicker shell.

### Rear shell tips (3D print)
- Get exact screen dimensions from the Touch Display 2 10" product brief / mechanical drawing before modeling. Active area is 135.4 × 216.6 mm.
- **Vent top and bottom** so air rises through the case like a chimney; leave clearance over the cooler fan.
- Openings for USB-C power, one USB-A (speaker), and a speaker grille facing forward or down.
- 0.3 mm clearance on fitted parts; heat-set inserts instead of printed threads.
- Recess a French cleat into the back so it hangs flat and lifts off for maintenance.

---

## Set up the Pi

1. Flash **Raspberry Pi OS (64-bit)** with Raspberry Pi Imager. In its settings set hostname `familyhub`, Wi-Fi, and enable SSH.
2. Connect the display (ribbon to the DSI port, power to GPIO 5V/GND) and boot.
3. Copy this folder over and run the installer:
   ```bash
   scp -r familyhub pi@familyhub.local:~
   ssh pi@familyhub.local
   cd familyhub && bash pi/install.sh
   ```
4. `sudo raspi-config` → System Options → Boot / Auto Login → **Desktop Autologin**.
5. Edit `config.json` (below), then `sudo reboot`. It boots straight into the calendar.

The installer sets up: the server as a systemd service, a full-screen Chromium kiosk,
landscape rotation (edit `pi/kiosk.sh` to stay portrait), and the screen turning off at
10 pm and back on at 6:30 am (`crontab -e` to change).

For typing on the screen, turn on Raspberry Pi OS's built-in on-screen keyboard in the
Raspberry Pi configuration tool (display settings). Quick-add means you rarely need much typing.

---

## Configure (`config.json`)

**Family members:** only used for the very first start. After that, manage people from the ⚙ Family screen in the app.

**Calendars:** every major service gives you a private iCal link. Paste it as `url`,
and set `member` to color it as that person (or `null` for shared).
- **Google:** Calendar settings → pick the calendar → *Integrate calendar* → **Secret address in iCal format**
- **iCloud:** Calendar app → share icon next to the calendar → **Public Calendar** → copy link (`webcal://` is fine)
- **Outlook:** Settings → Calendar → Shared calendars → **Publish a calendar** → ICS link

These links are read-only and private; treat them like passwords.

**Location** (`lat`/`lon`) for weather. **Timezone** as an IANA name.

**AI:** put an Anthropic API key in `anthropic_api_key` to turn on the morning message and
quick-add. It uses a small, cheap model by default (`ai_model`); a family's daily use costs
cents per month. Leave it blank and everything else still works.

**Voice:** see `voice/RECORDING_GUIDE.md`.

### Adding chores
There's no chore editor screen yet (see roadmap). For now add them from any computer
on your Wi-Fi:
```bash
curl -X POST http://familyhub.local:8080/api/chores \
  -d '{"title":"Feed the dog","member_id":4,"repeat":"daily","points":2}'
# repeat: "daily", "weekly:MO,WE,FR", or "once" with "due_date":"2026-10-12"
```
Member ids are in order of the `members` list (1, 2, 3…).

---

## How the "smart" parts work

| Feature | Where it runs | How |
|---|---|---|
| Conflicts, prep reminders, busy days, chore nudges | Pi | Rules over your calendar and chore history (`suggestions.py`) |
| Restock predictions | Pi | Learns each item's typical re-buy interval from list history (median gap); suggests it once overdue |
| Morning message, quick-add | Cloud (Claude API) | Sends today's events/chores, gets back plain text or event JSON (`ai.py`) |
| Dad's voice | Pi | Piper TTS with his fine-tuned model (`voice.py`) |

Every tap is logged to the `activity` table, so new learned features have history to
work from. Dismissed suggestions never come back.

---

## Files

```
server.py          HTTP server + JSON API
db.py              SQLite storage
ics.py             iCal reader with recurring events (no dependencies)
suggestions.py     on-device smart suggestions
ai.py              Claude API: morning message, quick-add
voice.py           Piper TTS wrapper for Dad's voice
web/               touchscreen UI (index.html, style.css, app.js)
pi/                installer, systemd service, kiosk + screen scripts
voice/             recording guide and prompts for Dad's voice
seed_demo.py       demo data
```

## Roadmap

1. **More settings screens** (PIN-locked): chores and calendars from the touchscreen, like the Family screen
2. **Meal planner** tied to the grocery list
3. **Photo frame mode** when idle (shared album)
4. **Wake word + voice commands** ("Hey Dad, add milk"): openWakeWord + Whisper on the Pi, Claude for intent
5. **Phone companion**: the same UI works on phones over home Wi-Fi today; add a home-screen icon and a sign-in for away-from-home access
6. **Smarter learning**: predict chore completion times, suggest who's free to drive, learn "usual" weekly events

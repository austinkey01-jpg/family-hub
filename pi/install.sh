#!/usr/bin/env bash
# FamilyHub installer for Raspberry Pi OS (64-bit, Bookworm or newer) on a Pi 5.
# Run from the familyhub folder:   bash pi/install.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(whoami)"
echo "Installing FamilyHub from $APP_DIR for user $USER_NAME"

sudo apt-get update
sudo apt-get install -y python3 python3-venv chromium-browser unclutter-xfixes wlr-randr || \
sudo apt-get install -y python3 python3-venv chromium unclutter wlr-randr

# Optional extras in a venv: full iCal recurrence support + Dad's voice (Piper).
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install icalendar recurring-ical-events piper-tts

# Config
[ -f "$APP_DIR/config.json" ] || cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"

# Backend service (starts on boot, restarts if it crashes)
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__USER__#$USER_NAME#g" \
    "$APP_DIR/pi/familyhub.service" | sudo tee /etc/systemd/system/familyhub.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now familyhub.service

# Kiosk browser on login (labwc / Wayland is the Bookworm+ default on Pi 5)
mkdir -p "$HOME/.config/labwc"
AUTOSTART="$HOME/.config/labwc/autostart"
grep -q familyhub-kiosk "$AUTOSTART" 2>/dev/null || echo "bash $APP_DIR/pi/kiosk.sh & # familyhub-kiosk" >> "$AUTOSTART"

# Screen schedule: dim/off at night, on in the morning (edit times in crontab -e)
( crontab -l 2>/dev/null | grep -v familyhub-screen ;
  echo "0 22 * * * bash $APP_DIR/pi/screen.sh off # familyhub-screen" ;
  echo "30 6 * * * bash $APP_DIR/pi/screen.sh on  # familyhub-screen" ) | crontab -

echo
echo "Done. Next:"
echo "  1. Edit $APP_DIR/config.json (family members, calendar links, location, API key)"
echo "  2. sudo raspi-config -> System Options -> Boot / Auto Login -> Desktop Autologin"
echo "  3. sudo reboot"

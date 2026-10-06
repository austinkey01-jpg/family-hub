#!/usr/bin/env bash
# Turn the touch display backlight on/off:  screen.sh on|off
# Touch Display 2 exposes its backlight under /sys/class/backlight.
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=wayland-0
OUT=$(wlr-randr 2>/dev/null | awk '/^DSI/{print $1; exit}')
if [ "$1" = "off" ]; then
  wlr-randr --output "${OUT:-DSI-2}" --off
else
  wlr-randr --output "${OUT:-DSI-2}" --on --transform 90
fi

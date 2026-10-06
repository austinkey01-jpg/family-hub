#!/usr/bin/env bash
# Full-screen browser pointed at FamilyHub. Launched from labwc autostart.

# The 10" Touch Display 2 is natively portrait. For a landscape wall display
# (like Skylight) rotate it; comment this out to keep portrait.
wlr-randr --output DSI-2 --transform 90 2>/dev/null || wlr-randr --output DSI-1 --transform 90 2>/dev/null || true

# Wait for the server
for i in $(seq 1 30); do curl -s localhost:8080 >/dev/null && break; sleep 1; done

BROWSER=$(command -v chromium-browser || command -v chromium)
exec "$BROWSER" \
  --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --disable-pinch --overscroll-history-navigation=0 --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --ozone-platform=wayland --enable-features=OverlayScrollbar \
  http://localhost:8080

#!/bin/bash
set -e

# Start Xvfb (virtual framebuffer) on display :99
Xvfb :99 -screen 0 1280x720x24 -ac &
sleep 2

# Start a lightweight window manager so windows display properly
fluxbox -display :99 &
sleep 1

# Start VNC server exposing the virtual display
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 -bg -o /tmp/x11vnc.log
sleep 1

# Start noVNC (web client) -> proxies VNC on port 6080
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 1

# Open xterm so the desktop isn't empty
xterm -display :99 -geometry 100x30+50+50 -fa 'Monospace' -fs 11 \
  -bg '#0d1117' -fg '#c9d1d9' \
  -T "nanobot terminal" \
  -e bash -c 'echo "  nanobot desktop ready"; echo "  Type: nanobot status"; echo ""; exec bash' &

# Open Chromium browser (used by Puppeteer, also useful for user)
# --no-sandbox is required when running as root inside a container
# Anti-detection flags make the browser appear as a regular user browser
_CHROME_UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
chromium --display=:99 --no-sandbox --no-first-run --no-default-browser-check \
  --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage \
  --remote-debugging-port=9222 \
  --window-size=1200,650 --window-position=80,30 \
  --disable-blink-features=AutomationControlled \
  --user-agent="$_CHROME_UA" \
  --lang=pt-BR \
  --disable-infobars \
  --disable-features=ChromeWhatsNewUI \
  "about:blank" &>/dev/null &

echo ""
echo "  ┌──────────────────────────────────────────┐"
echo "  │  Desktop ready!                          │"
echo "  │                                          │"
echo "  │  noVNC:  http://localhost:6080/vnc.html  │"
echo "  └──────────────────────────────────────────┘"
echo ""

# Run nanobot with all arguments
exec nanobot "$@"

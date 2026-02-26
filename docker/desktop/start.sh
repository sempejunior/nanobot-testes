#!/bin/bash
set -e

export PATH="/opt/nanobot/bin:$PATH"
export DISPLAY=:1

RESOLUTION="${VNC_RESOLUTION:-1280x720}"

echo "[*] Starting Xvfb..."
Xvfb :1 -screen 0 "${RESOLUTION}x24" -ac +extension GLX +render -noreset &
sleep 2

echo "[*] Starting XFCE desktop..."
startxfce4 &
sleep 3

echo "[*] Starting x11vnc..."
x11vnc -display :1 -rfbauth /root/.vnc/passwd -rfbport 5900 \
    -shared -forever -noxdamage -ncache 10 -q &
sleep 1

echo "[*] Starting noVNC on port 6080..."
websockify --web /usr/share/novnc 6080 localhost:5900 &

echo ""
echo "  ┌──────────────────────────────────────────┐"
echo "  │  Desktop ready!                          │"
echo "  │                                          │"
echo "  │  noVNC:  http://localhost:6080/vnc.html  │"
echo "  │  VNC:    localhost:5900                   │"
echo "  │  Pass:   nanobot                          │"
echo "  └──────────────────────────────────────────┘"
echo ""

# Keep container alive — wait for any background process
wait

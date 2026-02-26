FROM debian:bookworm-slim

ARG VNC_PASSWORD=nanobot
ARG VNC_RESOLUTION=1280x720

ENV DEBIAN_FRONTEND=noninteractive \
  VNC_PASSWORD=${VNC_PASSWORD} \
  VNC_RESOLUTION=${VNC_RESOLUTION} \
  DISPLAY=:1 \
  HOME=/root \
  LANG=en_US.UTF-8 \
  PATH="/opt/nanobot/bin:${PATH}"

# ── 1. System packages: desktop, VNC, browser, dev tools ─────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
  # Desktop environment
  xfce4 xfce4-terminal xfce4-taskmanager mousepad thunar \
  dbus-x11 at-spi2-core \
  # VNC: Xvfb (virtual framebuffer) + x11vnc (VNC server)
  xvfb x11vnc \
  # noVNC + websockify
  novnc python3-websockify \
  # Browser
  firefox-esr \
  # Dev / system tools
  curl wget ca-certificates gnupg git vim nano htop procps \
  sudo locales net-tools lsof unzip \
  xdotool imagemagick \
  # Python build deps
  python3-full python3-pip python3-venv \
  # Supervisor
  supervisor \
  && \
  # Locale setup
  sed -i 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen && \
  # Clean apt cache
  apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# ── 2. Node.js 20 (needed for WhatsApp bridge) ───────────────────────────────
RUN mkdir -p /etc/apt/keyrings && \
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
  > /etc/apt/sources.list.d/nodesource.list && \
  apt-get update && \
  apt-get install -y --no-install-recommends nodejs && \
  rm -rf /var/lib/apt/lists/*

# ── 3. uv (fast Python package manager) ──────────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
  ln -sf /root/.local/bin/uv /usr/local/bin/uv && \
  ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# ── 4. VNC password ──────────────────────────────────────────────────────────
RUN mkdir -p /root/.vnc && \
  x11vnc -storepasswd "$VNC_PASSWORD" /root/.vnc/passwd

# ── 5. Install nanobot in venv ────────────────────────────────────────────────
WORKDIR /app

# Create venv with system Python
RUN uv venv /opt/nanobot --python 3.11

# Deps layer (cached)
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p nanobot bridge && touch nanobot/__init__.py && \
  uv pip install --python /opt/nanobot/bin/python --no-cache . && \
  rm -rf nanobot bridge

# Full source
COPY nanobot/ nanobot/
COPY bridge/ bridge/
RUN uv pip install --python /opt/nanobot/bin/python --no-cache .

# Build WhatsApp bridge (optional, ignore errors)
WORKDIR /app/bridge
RUN npm install --ignore-scripts 2>/dev/null || true && \
  npm run build 2>/dev/null || true
WORKDIR /app

# Build the frontend web UI (optional, ignore errors)
WORKDIR /app/nanobot/web/frontend
RUN npm install --ignore-scripts 2>/dev/null || true && \
  npm run build 2>/dev/null || true
WORKDIR /app

# ── 6. Default nanobot config ─────────────────────────────────────────────────
RUN mkdir -p /root/.nanobot
COPY docker/desktop/config.json /root/.nanobot/config.json

# ── 7. Startup config ────────────────────────────────────────────────────────
COPY docker/desktop/supervisord.conf /etc/supervisor/conf.d/desktop.conf
COPY docker/desktop/start.sh /start.sh
RUN chmod +x /start.sh

# ── 8. Desktop shortcuts ─────────────────────────────────────────────────────
RUN mkdir -p /root/Desktop && \
  printf '[Desktop Entry]\nType=Application\nName=Terminal\nExec=xfce4-terminal\nIcon=utilities-terminal\nTerminal=false\n' \
  > /root/Desktop/terminal.desktop && \
  printf '[Desktop Entry]\nType=Application\nName=Nanobot Agent\nExec=xfce4-terminal -e "bash -c '\''nanobot agent; exec bash'\''"\nIcon=utilities-terminal\nTerminal=false\n' \
  > /root/Desktop/nanobot-agent.desktop && \
  printf '[Desktop Entry]\nType=Application\nName=Nanobot Status\nExec=xfce4-terminal -e "bash -c '\''nanobot status; exec bash'\''"\nIcon=dialog-information\nTerminal=false\n' \
  > /root/Desktop/nanobot-status.desktop && \
  printf '[Desktop Entry]\nType=Application\nName=Firefox\nExec=firefox-esr\nIcon=firefox-esr\nTerminal=false\n' \
  > /root/Desktop/firefox.desktop && \
  chmod +x /root/Desktop/*.desktop

# ── 9. Convenience aliases ────────────────────────────────────────────────────
RUN printf '\nalias ll="ls -la"\nalias nb="nanobot"\nalias nba="nanobot agent"\nalias nbg="nanobot gateway"\nalias nbs="nanobot status"\n' \
  >> /root/.bashrc && \
  printf '\nexport PATH="/opt/nanobot/bin:$PATH"\n' >> /root/.bashrc && \
  printf '\necho ""\necho "  ┌─────────────────────────────────────┐"\necho "  │  Nanobot Desktop Environment        │"\necho "  │                                     │"\necho "  │  nanobot status   - check status    │"\necho "  │  nanobot agent    - chat with agent  │"\necho "  │  nanobot gateway  - start gateway   │"\necho "  │  nanobot onboard  - initial setup   │"\necho "  │                                     │"\necho "  │  Config: ~/.nanobot/config.json     │"\necho "  └─────────────────────────────────────┘"\necho ""\n' \
  >> /root/.bashrc

# ── Ports ─────────────────────────────────────────────────────────────────────
# 6080 = noVNC (browser)
# 5900 = VNC direct
# 18790 = nanobot gateway
EXPOSE 6080 5900 18790

CMD ["/start.sh"]

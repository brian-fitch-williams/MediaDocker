#!/usr/bin/env bash
# Start Xvfb :1, XFCE, and RustDesk GUI. Used by headless-desktop-system.service.
set -euo pipefail

export DISPLAY="${DISPLAY:-:1}"
export HOME="${HOME:-/home/dell}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export XDG_SESSION_TYPE=x11
export DESKTOP_SESSION=xfce
export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_DESKTOP=xfce
# Avoid colliding with Cinnamon auto-login on :0
unset SESSION_MANAGER GDMSESSION GNOME_DESKTOP_SESSION_ID XDG_SEAT XDG_SEAT_PATH XDG_SESSION_PATH XDG_VTNR XDG_GREETER_DATA_DIR

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR" || true

cleanup() {
  local pid
  for pid in "${RUSTDESK_PID:-}" "${SESSION_PID:-}" "${XVFB_PID:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Drop a stale lock if a previous Xvfb died hard
if [[ -e "/tmp/.X1-lock" ]] && ! xdpyinfo -display :1 >/dev/null 2>&1; then
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true
fi

if ! xdpyinfo -display :1 >/dev/null 2>&1; then
  /usr/bin/Xvfb :1 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
  XVFB_PID=$!
  for _ in $(seq 1 40); do
    xdpyinfo -display :1 >/dev/null 2>&1 && break
    sleep 0.25
  done
  xdpyinfo -display :1 >/dev/null 2>&1 || {
    echo "Xvfb failed to provide DISPLAY=:1" >&2
    exit 1
  }
fi

/usr/bin/dbus-launch --exit-with-session /usr/bin/startxfce4 &
SESSION_PID=$!
sleep 2

/usr/bin/rustdesk &
RUSTDESK_PID=$!

# Stay up as long as the desktop session lives
wait "$SESSION_PID"

#!/bin/bash
# Start the media stack and RustDesk. Safe to run on every boot.
# RustDesk is started, not restarted: a restart rotates its one-time password.
set -euo pipefail

cd /home/dell/MediaDocker
docker compose up -d
systemctl start rustdesk.service

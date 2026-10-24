# Media stack (Sonarr · Radarr · Plex · NZBGet)

One Docker Compose project that brings up **Sonarr**, **Radarr**, **Plex Media Server**, and **NZBGet** together. Images are from [linuxserver.io](https://www.linuxserver.io/) (`lscr.io/linuxserver/...`).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (`docker compose version`)
- Enough disk for config + media under the paths you choose

## Quick start

```bash
cp .env.example .env   # optional; defaults work without it
docker compose up -d
```

All four services start. Check status with `docker compose ps` and logs with `docker compose logs -f`.

Stop with `docker compose down` (volumes on disk are kept).

## Ports

| Service | Default URL / port | Env override |
|---------|-------------------|--------------|
| Sonarr  | http://localhost:8989 | `SONARR_PORT` |
| Radarr  | http://localhost:7878 | `RADARR_PORT` |
| Plex    | http://localhost:32400/web | `PLEX_PORT` |
| NZBGet  | http://localhost:6789 | `NZBGET_PORT` |

Plex also publishes companion discovery ports (3005, 8324, 32469 TCP; 1900, 32410–32414 UDP) for LAN clients when using the default bridge network.

## Volumes

| Host path (default) | Used by | Inside container |
|---------------------|---------|------------------|
| `./config/sonarr` | Sonarr | `/config` |
| `./config/radarr` | Radarr | `/config` |
| `./config/plex` | Plex | `/config` |
| `./config/plex-transcode` | Plex | `/transcode` |
| `./config/nzbget` | NZBGet | `/config` |
| `./media/tv` | Sonarr, Plex | `/tv` |
| `./media/movies` | Radarr, Plex | `/movies` |
| `./downloads` | Sonarr, Radarr, NZBGet | `/downloads` |

Override roots with `CONFIG_DIR`, `TV_DIR`, `MOVIES_DIR`, `DOWNLOADS_DIR`, and `PLEX_TRANSCODE_DIR` in `.env`.

Shared `./downloads` lets Sonarr/Radarr import completed NZBGet downloads without cross-container copy tricks. Point Sonarr/Radarr download clients at NZBGet (`nzbget:6789` on the compose network, or `localhost:6789` from the host).

## Environment variables

See [`.env.example`](.env.example). Important ones:

| Variable | Purpose | Default |
|----------|---------|---------|
| `PUID` / `PGID` | File ownership inside containers | `1000` / `1000` |
| `TZ` | Timezone | `Etc/UTC` |
| `PLEX_CLAIM` | One-time Plex claim token | empty |
| `NZBGET_USER` / `NZBGET_PASS` | NZBGet web login | `nzbget` / `tegbzn6789` |

Match `PUID`/`PGID` to your host user (`id -u` / `id -g`) so media files stay writable.

## First-run tips

### Plex claim token

1. Sign in at [https://plex.tv/claim](https://plex.tv/claim) and copy the token (valid ~4 minutes).
2. Set `PLEX_CLAIM=claim-...` in `.env`, then `docker compose up -d plex` (or recreate: `docker compose up -d --force-recreate plex`).
3. Open http://localhost:32400/web, finish setup, add libraries pointing at `/tv` and `/movies`.
4. Clear `PLEX_CLAIM` afterward; it is only needed for the initial claim.

**Host networking (Linux):** if clients cannot discover Plex on the LAN, edit `docker-compose.yml`: comment out the `ports:` block under `plex` and uncomment `network_mode: host`. With host mode, published port mappings are ignored; use http://localhost:32400/web directly. On Docker Desktop (macOS/Windows), stick with the default bridge + published ports.

### NZBGet credentials

Default web UI login is **nzbget** / **tegbzn6789** (linuxserver image defaults). Change via `NZBGET_USER` / `NZBGET_PASS` before first start, or in Settings → Security after login. Configure your Usenet provider under Settings → News-Servers.

### Wire Sonarr / Radarr to NZBGet

In Sonarr and Radarr:

1. **Settings → Download Clients → NZBGet**
2. Host: `nzbget` (compose service name) or `host.docker.internal` / host IP if needed
3. Port: `6789`
4. Username / password: same as NZBGet web UI
5. Category: e.g. `tv` / `movies` (create matching categories in NZBGet if you use them)

Root folders: Sonarr → `/tv`, Radarr → `/movies`. Completed downloads path should match the shared `/downloads` volume layout NZBGet writes to.

### Permissions

If imports fail with permission errors, align `PUID`/`PGID` with the owner of `./media` and `./downloads`, then recreate the affected containers.

## Layout

```
.
├── docker-compose.yml   # Sonarr, Radarr, Plex, NZBGet
├── .env.example         # Paths, ports, PUID/PGID/TZ, claim token
├── config/              # Per-app config (created on first run)
├── media/tv             # TV library
├── media/movies         # Movie library
└── downloads            # NZBGet output → *arr import
```

## Scope

This repo is only the four-service compose stack—no auth gateway, databases, reverse proxy, or extra downloaders. Add those later if you need them.

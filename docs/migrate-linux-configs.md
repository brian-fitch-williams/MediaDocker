# Migrate Linux host configs → MediaDocker (Mac)

Practical guide to move existing Sonarr / Radarr / NZBGet / Plex settings into the volume mounts used by this compose stack:

| Host path (repo) | Container path |
|------------------|----------------|
| `./config/sonarr` | `/config` |
| `./config/radarr` | `/config` |
| `./config/plex` | `/config` |
| `./config/nzbget` | `/config` |
| `./media/tv` | `/tv` |
| `./media/movies` | `/movies` |
| `./downloads` | `/downloads` |

## Your host (shaka / labuser) — read this first

Your Linux startup script implies a **mixed** install, not a uniform Docker stack:

```bash
#!/bin/bash
/home/labuser/nzbget/nzbget -D
mono /opt/NzbDrone/NzbDrone.exe
docker start radarr
```

| App | How it runs on `shaka` | Where config almost certainly lives |
|-----|------------------------|-------------------------------------|
| **NZBGet** | Native binary under `/home/labuser/nzbget/` | `nzbget.conf` in that directory (or rarely `~/.nzbget`) |
| **Sonarr** | Classic **NzbDrone** Mono install at `/opt/NzbDrone/` | Usually `/home/labuser/.config/NzbDrone` (Sonarr **v2**-era AppData) |
| **Radarr** | Already Docker (`docker start radarr`) | Whatever `docker inspect radarr` shows for `/config` (and media mounts) |
| **Plex** | Native package (confirmed via `ps`) — **not** Docker | `/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/` |
| **Media** | On-host under `kodihome` | e.g. TV under `/home/labuser/kodihome/...` → map into `./media/tv` + `./media/movies` |

**Plex on `shaka` (confirmed):** binary `/usr/lib/plexmediaserver/Plex Media Server`, version `1.41.6.9685-d301f511a`, VAAPI HW transcode on `/dev/dri/renderD128` (i965). **Mac Docker Desktop has no `/dev/dri` / VAAPI** — expect CPU transcode only after the move.

Bake these paths into every copy step below. Do not assume linuxserver-style `/config` layouts on the Linux box except for Radarr.

---

## Do this tonight (shortest checklist)

On **`shaka` as `labuser`** (stop everything first):

1. Stop old services so DBs are consistent:
   ```bash
   # NZBGet native daemon
   /home/labuser/nzbget/nzbget -Q || true
   # Sonarr (NzbDrone) — kill the mono process if no service unit
   pkill -f 'NzbDrone.exe' || true
   # Radarr container
   docker stop radarr
   # Plex native package (confirmed on shaka)
   sudo systemctl stop plexmediaserver
   ```
2. On the Mac, stop MediaDocker: `docker compose down` in the project dir.
3. Confirm sources on `shaka`:
   ```bash
   ls -la /home/labuser/nzbget/nzbget.conf
   ls -la /home/labuser/.config/NzbDrone
   docker inspect radarr --format '{{json .Mounts}}' | python3 -m json.tool
   ls -la "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/"
   ls -la /home/labuser/kodihome/   # media root example
   ```
4. `rsync`/`scp` into the Mac project (adjust `MAC` / `DEST`):
   ```bash
   MAC=user@mac-hostname
   DEST='~/MediaDocker'   # or wherever you cloned this repo

   rsync -avh /home/labuser/nzbget/nzbget.conf "$MAC:$DEST/config/nzbget/"
   rsync -avh /home/labuser/nzbget/ "$MAC:$DEST/config/nzbget-native-backup/"

   rsync -avh /home/labuser/.config/NzbDrone/ "$MAC:$DEST/config/sonarr/"

   # After inspect: replace SRC with Radarr's host /config mount
   rsync -avh /path/from/inspect/radarr-config/ "$MAC:$DEST/config/radarr/"

   # Plex → linuxserver layout under ./config/plex
   rsync -avh --progress \
     --exclude 'Cache/' --exclude 'Crash Reports/' --exclude 'Updates/' \
     "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/" \
     "$MAC:$DEST/config/plex/Library/Application Support/Plex Media Server/"

   # Media from kodihome (split/rename into tv + movies as needed)
   rsync -avh --progress /home/labuser/kodihome/ "$MAC:$DEST/media/kodihome-backup/"
   # Then place (or symlink) series under media/tv and films under media/movies
   ```
5. Fix **NZBGet** `nzbget.conf` WebDir/ConfigTemplate for linuxserver (white UI) — see [NZBGet](#nzbget-native--linuxserver-docker).
6. Remap paths in Sonarr/Radarr/NZBGet/Plex to `/tv`, `/movies`, `/downloads`.
7. On Mac: set `PUID`/`PGID` in `.env`, `chown` if needed, then `docker compose up -d`.
8. Open UIs; NZBGet: **http://localhost:6789/** then **http://localhost:6789/nzbget/**. Plex: expect **CPU transcode only** (no VAAPI).
9. Keep Linux services stopped until Mac looks good; rollback = start the old script + `systemctl start plexmediaserver` and `compose down` on Mac.

---

## Order of operations (full)

1. **Inventory** on Linux: confirm paths, note absolute media/download roots.
2. **Stop** Linux services/containers **and** Mac MediaDocker containers.
3. **Backup** on Linux (tar/rsync to another disk) before any destructive edit.
4. **Copy** configs into `./config/...` on the Mac project.
5. **Do not start** containers until path remaps + NZBGet WebDir fixes are done.
6. **Permissions**: align ownership with `PUID`/`PGID`.
7. **Start** MediaDocker; verify logs; fix remaps iteratively.
8. **Wire** Sonarr/Radarr → NZBGet host `nzbget:6789`.
9. **Only then** point apps at live media and resume downloads.
10. **Rollback**: leave Mac stack down; restart native NZBGet + NzbDrone + `docker start radarr` (+ Plex) on `shaka`.

---

## Finding config dirs on Linux

### Quick discovery commands

```bash
# What is listening / running?
ps aux | egrep -i 'nzbget|NzbDrone|sonarr|radarr|plex' | grep -v grep
ss -lntp | egrep '6789|8989|7878|32400' || netstat -lntp | egrep '6789|8989|7878|32400'

# systemd units (if any)
systemctl list-units --type=service --all | egrep -i 'sonarr|radarr|nzbget|plex'

# Docker (Radarr on your box; maybe Plex too)
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker inspect radarr --format '{{json .Mounts}}' | python3 -m json.tool
```

### Typical install layouts (generic)

| Install style | Where config usually is |
|---------------|-------------------------|
| Native package (apt/yum) | `/var/lib/<app>`, `/etc/<app>`, or `~/.config/<App>` |
| Manual / home binary (your NZBGet) | Same directory as the binary (`/home/labuser/nzbget/`) |
| Mono NzbDrone (your Sonarr) | `/opt/NzbDrone` = program; AppData often `~/.config/NzbDrone` |
| Docker on Linux (your Radarr) | Host path from `docker inspect` bind mount or named volume under `/var/lib/docker/volumes/` |
| Snap | `~/snap/<app>/current/...` or `/var/snap/<app>/...` |

---

## What to copy (and what not to)

### NZBGet (native → `./config/nzbget`)

**Copy:**

- `/home/labuser/nzbget/nzbget.conf` → `./config/nzbget/nzbget.conf` (required)
- Optional: `scripts/`, custom certs, RSS state if stored beside the binary
- Queue/history under the native `MainDir` only if you want in-progress downloads (usually skip; start clean)

**Do not blindly reuse host paths inside the conf.** After copy, edit (or sed) these for the linuxserver image:

| Setting | Typical linuxserver value |
|---------|---------------------------|
| `MainDir` | `/config` |
| `WebDir` | `${AppDir}/webui` or `/app/nzbget/webui` |
| `ConfigTemplate` | `${AppDir}/webui/nzbget.conf.template` |
| `DestDir` | `/downloads/completed` |
| `InterDir` | `/downloads/intermediate` |
| `NzbDir` / `QueueDir` / `TempDir` / `ScriptDir` | under `/config/...` or `/downloads/...` as you prefer |
| `LogFile` | `/config/nzbget.log` |

Native installs often leave `WebDir=` empty (daemon gets paths via CLI) or point at `/home/labuser/nzbget/webui`. That **breaks** the linuxserver UI and is a prime cause of a **blank white page** at port 6789. Fix `WebDir` + `ConfigTemplate` before `compose up`, or temporarily move `nzbget.conf` aside and let the image generate a fresh one, then re-enter news-server settings.

See also [NZBGet white page](../README.md#nzbget-blank-white-page) in the README.

### Sonarr / NzbDrone (v2 Mono → `./config/sonarr`)

Your layout is **Sonarr v2-era** (`NzbDrone.exe` under `/opt/NzbDrone`). linuxserver `sonarr` images are **v3/v4**. This is **not** a guaranteed drop-in.

**Find AppData:**

```bash
# Working directory / open files of the running process (stop after noting)
pgrep -af NzbDrone
# Common default for the labuser account:
ls -la /home/labuser/.config/NzbDrone
# Sometimes people used a custom data dir; check for config.xml:
find /home/labuser /opt/NzbDrone -name 'config.xml' 2>/dev/null
```

**Copy the AppData tree** (contains `config.xml`, `nzbdrone.db` / `sonarr.db`, logs folder, etc.) into `./config/sonarr/`.

**Do not copy** the `/opt/NzbDrone` program binaries into Docker — only AppData.

**Upgrade risks (v2 → v3/v4):**

- Database schema upgrades run on first start; **back up** AppData first.
- Very old v2 DBs may fail to upgrade; if Sonarr refuses to start, check `docker compose logs sonarr`. Recovery options: restore backup and try an intermediate Sonarr version, or export library/lists from the old UI before cutover and re-add on a fresh v4 config.
- After upgrade, **re-check** root folders (`/tv`), download client, indexers, and remote path mappings.
- API keys and ports in `config.xml` usually survive; URL base / authentication settings may need a pass.

### Radarr (existing Docker → `./config/radarr`)

Prefer **rsync from the current container mount**, not reinventing:

```bash
docker inspect radarr --format '{{json .Mounts}}' | python3 -m json.tool
# Note Source for Destination "/config", and any /movies or /downloads binds
docker stop radarr
rsync -avh /actual/host/config/path/  user@mac:~/MediaDocker/config/radarr/
```

If `/config` is a **named volume**:

```bash
docker run --rm -v radarr_config:/from:ro -v "$PWD":/backup alpine \
  tar czf /backup/radarr-config.tgz -C /from .
# scp radarr-config.tgz to Mac, extract into ./config/radarr/
```

Also note media/download host paths from inspect so you can rsync libraries into `./media/movies` and `./downloads` if desired.

### Plex (native package on `shaka` → `./config/plex`)

**Confirmed on host:**

| Item | Value |
|------|--------|
| Binary | `/usr/lib/plexmediaserver/Plex Media Server` |
| Version | `1.41.6.9685-d301f511a` |
| Library root | `/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/` |
| Media example | `/home/labuser/kodihome/...` (TV under `kodihome`) |
| HW transcode | VAAPI via `/dev/dri/renderD128` (i965) |

**Stop before copy:**

```bash
sudo systemctl stop plexmediaserver
# Confirm stopped:
systemctl status plexmediaserver
pgrep -a 'Plex Media Server' || echo 'plex stopped'
```

**linuxserver/plex layout:** the container mounts host `./config/plex` at `/config`. The Application Support tree must live at:

```text
./config/plex/Library/Application Support/Plex Media Server/
```

which is `/config/Library/Application Support/Plex Media Server/` inside the container — the same relative structure as the Debian/Ubuntu package under `/var/lib/plexmediaserver/`.

**Copy:**

```bash
sudo rsync -avh --progress \
  --exclude 'Cache/' \
  --exclude 'Crash Reports/' \
  --exclude 'Updates/' \
  "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/" \
  "$MAC:$DEST/config/plex/Library/Application Support/Plex Media Server/"
```

Use `sudo` on the read side if files are owned by `plex`. After rsync to the Mac, `chown` to your Mac user / `PUID`.

**Do not copy (or exclude):**

- `Cache/` (Relay host keys, photo/transcoder caches — regenerate)
- `Crash Reports/`, `Updates/`
- Optional: `Codecs/` (re-downloaded)
- Any assumption of `/dev/dri` device nodes

**Media (`kodihome`) → compose mounts:**

1. Rsync `/home/labuser/kodihome/` to the Mac (full tree or only the libraries you still want).
2. Arrange content so compose can mount:
   - TV → `./media/tv` → container `/tv`
   - Movies → `./media/movies` → container `/movies`
3. After Plex starts on Mac, **edit each library** in Plex to replace `/home/labuser/kodihome/...` with `/tv` or `/movies`. Old absolute paths will not resolve inside the container.

**HW transcode / Mac Docker Desktop:**

- Linux used VAAPI on `renderD128`. This compose file does **not** pass `/dev/dri` (and Docker Desktop on Mac **cannot** expose Intel VAAPI like the bare-metal host).
- After migration: **CPU transcode only**. Disable “Use hardware acceleration when available” if it misbehaves, or leave it on — Plex will fall back when no device exists.
- Do not add `/dev/dri` device mappings expecting them to work on Mac.

**Claim / server identity when moving hosts:**

- Copying `Preferences.xml` + databases preserves much of the server identity, but a **new machine** (Linux → Mac) often still needs a [claim token](https://plex.tv/claim) (`PLEX_CLAIM` in `.env`) or a sign-in to restore remote access.
- If the server appears duplicate or “unclaimed,” claim once, then clear `PLEX_CLAIM`.
- Keep the Linux Library backup until playback and remote access look right.

---

## Permissions: PUID/PGID (Mac Docker Desktop vs Linux)

linuxserver images run app processes as `abc` mapped to `PUID`/`PGID`.

| Host | Guidance |
|------|----------|
| **Linux** | Set `PUID`/`PGID` to `id -u` / `id -g` of the user that owns media files (on `shaka`, often `labuser` → check `id labuser`). `chown -R $PUID:$PGID` the config/media/downloads trees. |
| **Docker Desktop (Mac)** | VM maps file ownership; `PUID=1000` `PGID=1000` (compose defaults) usually works. If writes fail, still set those env vars and ensure your Mac user can write the project dirs (`chmod`/`chown` on the Mac side). Avoid `chmod -R 777` long-term. |

```bash
# On Mac project root after rsync (example)
sudo chown -R "$(id -u):$(id -g)" config media downloads
# Or match .env:
# sudo chown -R 1000:1000 config media downloads
```

---

## Path remapping (*arr, NZBGet, Plex)

Old Linux absolute paths **inside** app DBs/config must become container paths:

| Role | Container path in this stack |
|------|------------------------------|
| TV library | `/tv` |
| Movies library | `/movies` |
| Downloads (shared) | `/downloads` |

**Sonarr / Radarr UI:** Settings → Media Management → Root Folders; Download Clients; Remote Path Mappings (delete obsolete Linux mappings or map host→container if any remote client remains).

**DB note:** Root folders live in the SQLite DB. Changing only host mounts is not enough — update inside the app (or with sqlite only if you know what you are doing, after backup).

**NZBGet:** edit `DestDir` / `InterDir` / categories paths in `nzbget.conf` or Settings → PATHS / CATEGORIES.

**Plex:** Edit each library’s folders to `/tv` or `/movies`.

---

## NZBGet (native → linuxserver Docker)

### `nzbget.conf`, WebDir, ConfigTemplate

linuxserver image ([docs](https://docs.linuxserver.io/images/docker-nzbget/)):

- Web UI primary URL: **http://localhost:6789/** (root `/`)
- Built-in alias: **http://localhost:6789/nzbget/** (trailing slash matters for the alias)
- **No `WEB_ROOT` environment variable**

Defaults baked into the image template:

- `WebDir=${AppDir}/webui`
- `ConfigTemplate=${AppDir}/webui/nzbget.conf.template`
- `MainDir=/config`
- `DestDir=/downloads/completed`
- `InterDir=/downloads/intermediate`

Your native daemon (`/home/labuser/nzbget/nzbget -D`) almost certainly has different PATH values. Migrating the conf **without** fixing `WebDir`/`ConfigTemplate` is the usual reason the linuxserver container serves a **blank white page** while Sonarr/Radarr/Plex look fine.

**Safe repair sequence:**

1. Backup `./config/nzbget/nzbget.conf`.
2. Set `WebDir` and `ConfigTemplate` to the linuxserver values above.
3. Point download dirs at `/downloads/...`.
4. Recreate: `docker compose up -d --force-recreate nzbget`.
5. If still blank: check `docker compose logs nzbget` for “Could not read configuration templates” / 503; hard-refresh the browser; try `/nzbget/`.
6. Nuclear option: move conf aside, start once for a fresh conf, re-enter news servers / categories.

---

## rsync / scp from `shaka` to the Mac project

```bash
# From shaka — examples (stop services first)
PROJECT='user@mac:~/path/to/MediaDocker'

rsync -avh --progress \
  /home/labuser/nzbget/nzbget.conf \
  "$PROJECT/config/nzbget/"

rsync -avh --progress \
  /home/labuser/.config/NzbDrone/ \
  "$PROJECT/config/sonarr/"

# Radarr config Source from docker inspect
rsync -avh --progress \
  /path/from/inspect/radarr-config/ \
  "$PROJECT/config/radarr/"

# Media libraries (optional, large)
rsync -avh --progress /path/to/tv/ "$PROJECT/media/tv/"
rsync -avh --progress /path/to/movies/ "$PROJECT/media/movies/"

# scp one-off tarball alternative
tar czf /tmp/mediaconfigs.tgz \
  -C /home/labuser nzbget/. \
  -C /home/labuser .config/NzbDrone
scp /tmp/mediaconfigs.tgz user@mac:~/
```

Exclude caches when copying Plex:

```bash
rsync -avh --progress \
  --exclude 'Cache/' --exclude 'Crash Reports/' --exclude 'Updates/' \
  "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/" \
  "$PROJECT/config/plex/Library/Application Support/Plex Media Server/"
```

---

## Rollback

1. On Mac: `docker compose down` (do not delete `./config` until you are sure).
2. On `shaka`: start the old stack again:
   ```bash
   /home/labuser/nzbget/nzbget -D
   mono /opt/NzbDrone/NzbDrone.exe &
   docker start radarr
   sudo systemctl start plexmediaserver
   ```
3. If you only copied (never deleted) Linux data, rollback is immediate. If you edited Linux confs in place, restore from the backup tarball taken earlier.

---

## After cutover sanity checks

- [ ] Sonarr http://localhost:8989 — root folder `/tv`, download client → `nzbget:6789`
- [ ] Radarr http://localhost:7878 — root folder `/movies`, same NZBGet client
- [ ] NZBGet http://localhost:6789/ (or `/nzbget/`) — login works; DestDir under `/downloads`
- [ ] Plex http://localhost:32400/web — libraries remapped off `kodihome` to `/tv` and `/movies`; claim/remote OK; HW accel off or ignored (CPU only on Mac)
- [ ] Test one TV + one movie grab through NZBGet → *arr import
- [ ] Only then disable the Linux startup script / `plexmediaserver` on `shaka`

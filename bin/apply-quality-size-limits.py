#!/usr/bin/env python3
"""Apply Sonarr/Radarr quality max-size caps for direct-play-friendly files.

Units are MB/min for both apps. Formula: MB/min = Mbps * 7.5

Reads ApiKey from each app's config.xml (default: $CONFIG_DIR or ./config).
Only updates minSize/maxSize (and preferredSize when it would exceed max).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def mb_from_mbps(mbps: float) -> float:
    return mbps * 7.5


def read_api_key(config_xml: Path) -> tuple[str, int]:
    root = ET.parse(config_xml).getroot()
    key = root.findtext("ApiKey")
    port = int(root.findtext("Port") or "0")
    if not key or not port:
        raise SystemExit(f"Missing ApiKey/Port in {config_xml}")
    return key, port


def api(method: str, url: str, key: str, data=None):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "X-Api-Key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    body = None if data is None else json.dumps(data).encode()
    with urllib.request.urlopen(req, data=body) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def clamp_preferred(q: dict, new_max: float | None) -> None:
    if new_max is None:
        return
    pref = q.get("preferredSize")
    if pref is not None and pref >= new_max:
        q["preferredSize"] = max(0, new_max - 5)


def sonarr_max(name: str) -> float | None:
    n = name.lower()
    if "unknown" in n:
        return None
    if "raw" in n:
        return mb_from_mbps(40)
    if "2160" in n and "remux" in n:
        return mb_from_mbps(70)
    if "2160" in n:
        return mb_from_mbps(60)
    if "1080" in n and "remux" in n:
        return mb_from_mbps(30)
    if "1080" in n:
        return mb_from_mbps(24)  # ~20-25 Mbps TV
    if "720" in n:
        return mb_from_mbps(16)
    if "576" in n or "480" in n or n in ("sdtv", "dvd"):
        return mb_from_mbps(8)
    return mb_from_mbps(24)


def radarr_max(name: str) -> float:
    # Radarr treats maxSize >= 400 (or null) as Unlimited.
    n = name.lower()
    if "unknown" in n or n in (
        "workprint",
        "cam",
        "telesync",
        "telecine",
        "regional",
        "dvdscr",
    ):
        return mb_from_mbps(8)
    if "br-disk" in n or n == "br-disk":
        return mb_from_mbps(40)
    if "raw" in n:
        return mb_from_mbps(40)
    if "2160" in n:
        return 399.0  # ~53 Mbps finite ceiling
    if "1080" in n and ("remux" in n or "bluray" in n):
        return mb_from_mbps(40)
    if "1080" in n:
        return mb_from_mbps(30)
    if "720" in n:
        return mb_from_mbps(20)
    if "576" in n or "480" in n or "dvd" in n or n == "sdtv":
        return mb_from_mbps(8)
    return mb_from_mbps(30)


def apply(host: str, port: int, key: str, max_fn, dry_run: bool) -> None:
    url = f"http://{host}:{port}/api/v3/qualitydefinition"
    defs = api("GET", url, key)
    updates = []
    for q in defs:
        qname = (q.get("quality") or {}).get("name") or q.get("title") or ""
        new_max = max_fn(qname)
        if new_max is None:
            print(f"  skip {qname}")
            continue
        q2 = copy.deepcopy(q)
        mn = q2.get("minSize") or 0
        if mn >= new_max:
            q2["minSize"] = max(0, new_max - 20)
        before = q.get("maxSize")
        q2["maxSize"] = float(new_max)
        clamp_preferred(q2, float(new_max))
        updates.append(q2)
        print(f"  {qname}: max {before} -> {q2['maxSize']}")
    if dry_run:
        print(f"  dry-run: would update {len(updates)} rows")
        return
    api("PUT", f"{url}/update", key, updates)
    print(f"  updated {len(updates)} rows")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config-dir",
        default=os.environ.get("CONFIG_DIR", "./config"),
        help="Directory containing sonarr/ and radarr/ config.xml",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sonarr-only", action="store_true")
    p.add_argument("--radarr-only", action="store_true")
    args = p.parse_args()
    base = Path(args.config_dir)

    if not args.radarr_only:
        key, port = read_api_key(base / "sonarr" / "config.xml")
        print(f"Sonarr :{port}")
        apply(args.host, port, key, sonarr_max, args.dry_run)
    if not args.sonarr_only:
        key, port = read_api_key(base / "radarr" / "config.xml")
        print(f"Radarr :{port}")
        apply(args.host, port, key, radarr_max, args.dry_run)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        raise SystemExit(1)

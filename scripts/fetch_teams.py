"""
Fetch all EA FC 26 clubs from futbin.com and download their logos.
Generates data/teams.json with team metadata and logo paths.

Usage: python scripts/fetch_teams.py
"""

import json
import os
import re
import urllib.request
import urllib.parse
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOGOS_DIR = BASE_DIR / "public" / "logos"
DATA_DIR = BASE_DIR / "data"
FUTBIN_URL = "https://www.futbin.com/clubs"

LOGOS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_clubs_page():
    req = urllib.request.Request(FUTBIN_URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_clubs(html):
    clubs = []
    seen_ids = set()

    img_pattern = r'<img[^>]*src="(https://cdn3\.futbin\.com/content/fifa26/img/clubs/dark/(\d+)\.png[^"]*)"'
    link_pattern = r'<a[^>]*href="/26/clubs/(\d+)/[^"]*"[^>]*>([^<]+)</a>'

    img_matches = re.findall(img_pattern, html)
    link_matches = re.findall(link_pattern, html)

    id_to_name = {}
    for club_id, name in link_matches:
        if club_id not in id_to_name:
            id_to_name[club_id] = name

    for full_url, club_id in img_matches:
        if club_id in seen_ids:
            continue
        seen_ids.add(club_id)

        name = id_to_name.get(club_id, f"Club {club_id}")

        download_url = full_url.replace("&amp;", "&")

        clubs.append({
            "id": int(club_id),
            "name": name,
            "logoUrl": download_url,
            "logoPath": f"/logos/{club_id}.png",
        })

    return clubs


def download_logo(club):
    filepath = LOGOS_DIR / f"{club['id']}.png"
    if filepath.exists() and filepath.stat().st_size > 0:
        return True

    for attempt in range(2):
        try:
            req = urllib.request.Request(club["logoUrl"], headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.futbin.com/clubs",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if len(data) > 100:
                    filepath.write_bytes(data)
                    return True
                else:
                    print(f"  Too small ({len(data)}B): {club['name']}")
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
            else:
                print(f"  Failed: {club['name']} (id={club['id']}) — {e}")
    return False


def main():
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("Fetching futbin clubs page...")
    html = fetch_clubs_page()

    clubs = parse_clubs(html)
    print(f"Found {len(clubs)} clubs")

    if not clubs:
        print("ERROR: No clubs parsed.")
        return

    print(f"\nSample clubs:")
    for c in clubs[:5]:
        print(f"  {c['id']}: {c['name']}")
    print(f"  ...")
    for c in clubs[-3:]:
        print(f"  {c['id']}: {c['name']}")

    print(f"\nDownloading logos to {LOGOS_DIR}...")
    success = 0
    fail = 0
    for i, club in enumerate(clubs):
        if download_logo(club):
            success += 1
        else:
            fail += 1

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(clubs)} ({success} ok, {fail} failed)")
            time.sleep(1)

    print(f"\nDone: {success} downloaded, {fail} failed out of {len(clubs)}")

    teams = []
    for club in clubs:
        logo_file = LOGOS_DIR / f"{club['id']}.png"
        if logo_file.exists() and logo_file.stat().st_size > 0:
            teams.append({
                "id": club["id"],
                "name": club["name"],
                "logoPath": club["logoPath"],
            })

    output_path = DATA_DIR / "teams.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(teams)} teams (with valid logos) to {output_path}")


if __name__ == "__main__":
    main()

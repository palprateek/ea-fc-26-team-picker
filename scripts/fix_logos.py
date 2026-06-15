#!/usr/bin/env python3
"""
Fix mismatched team logos by scraping football-logos.cc to build a correct
team-name → logo-slug mapping, then reassigning SVG files and downloading
PNGs for any gaps.

Usage: python scripts/fix_logos.py
"""

import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

from difflib import SequenceMatcher
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
TEAMS_JSON = os.path.join(PROJECT_DIR, "data", "teams.json")
LOGOS_DIR = os.path.join(PROJECT_DIR, "public", "logos")

COUNTRIES = [
    "england", "spain", "germany", "italy", "france", "portugal",
    "netherlands", "belgium", "scotland", "turkey", "austria",
    "usa", "saudi-arabia", "brazil", "argentina", "mexico",
    "norway", "sweden", "denmark", "poland", "south-korea", "china",
    "australia", "colombia", "chile", "peru", "ecuador", "paraguay",
    "romania", "croatia", "greece", "republic-of-ireland", "hungary",
    "czech-republic", "ukraine", "india", "bolivia", "venezuela",
    "haiti", "congo-dr", "japan", "uruguay", "switzerland", "new-zealand",
]

FUTBIN_CDN = "https://cdn3.futbin.com/content/fifa26/img/clubs/dark"


def normalize_name(name: str) -> str:
    name = re.sub(r"\s+logo\s*$", "", name, flags=re.IGNORECASE)
    name = name.lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    # Strip year suffixes like 1907, 1912, etc.
    name = re.sub(r"\b(19|20)\d{2}\b", "", name)
    for suffix in [" fc", " cf", " sc", " de", " da", " do", " del", " la",
                    " le", " les", " los", " cd", " ud", " rc", " ac",
                    " as", " ss", " us", " sp", " sv", " tsv", " vfl",
                    " bsc", " fsv", " sk", " fk", " ifk", " bk",
                    " united", " city", " town", " athletic", " fc.",
                    " cf.", " sc.", " ii", " b", " iii"]:
        name = re.sub(re.escape(suffix) + r"\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(".")
    return name


def fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def fetch_country_page(country: str) -> list[dict]:
    url = f"https://football-logos.cc/{country}/"
    print(f"  Fetching {url} ...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FIFAFixLogos/1.0)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return []

    entries = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        _extract_entries(data, entries, country)

    print(f"  Found {len(entries)} team entries")
    return entries


def _extract_entries(obj, out: list, country: str):
    """Extract team entries from JSON-LD. The structure is:
    CollectionPage -> mainEntity -> itemListElement -> ListItem[]
    Each ListItem has: url (with slug), item.name, item.contentUrl
    """
    if isinstance(obj, dict):
        # Check for mainEntity with itemListElement (CollectionPage)
        main_entity = obj.get("mainEntity", {})
        if isinstance(main_entity, dict):
            items = main_entity.get("itemListElement", [])
            if isinstance(items, list):
                for list_item in items:
                    if not isinstance(list_item, dict):
                        continue
                    url = list_item.get("url", "")
                    item_obj = list_item.get("item", {})
                    if not isinstance(item_obj, dict) or not url:
                        continue
                    name = item_obj.get("name", "")
                    content_url = item_obj.get("contentUrl", "")
                    if isinstance(name, str) and name:
                        slug = url.rstrip("/").split("/")[-1]
                        raw_name = re.sub(r"\s+logo\s*$", "", name, flags=re.IGNORECASE).strip()
                        if raw_name and slug:
                            out.append({
                                "name": raw_name,
                                "slug": slug,
                                "country": country,
                                "contentUrl": content_url if isinstance(content_url, str) else "",
                            })
        # Also check for top-level itemListElement (fallback)
        elif "itemListElement" in obj:
            for item in obj["itemListElement"]:
                _extract_entries(item, out, country)
    elif isinstance(obj, list):
        for item in obj:
            _extract_entries(item, out, country)


def download_file(url: str, filepath: str) -> bool:
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.futbin.com/clubs",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) > 200:
                    with open(filepath, "wb") as f:
                        f.write(data)
                    return True
                else:
                    print(f"    Too small ({len(data)}B): {url}")
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
            else:
                print(f"    Download failed: {url} — {e}")
    return False


def main():
    print(f"Reading teams from {TEAMS_JSON}")
    with open(TEAMS_JSON, "r", encoding="utf-8") as f:
        teams = json.load(f)
    print(f"Loaded {len(teams)} teams\n")

    # Step 1: Scrape football-logos.cc for all countries
    print("=== Step 1: Scrape football-logos.cc ===")
    all_site_entries = []
    for country in COUNTRIES:
        entries = fetch_country_page(country)
        all_site_entries.extend(entries)
        time.sleep(1)

    print(f"\nTotal site entries scraped: {len(all_site_entries)}")

    # Build normalized name → entry mapping from site
    site_by_norm: dict[str, list[dict]] = {}
    for entry in all_site_entries:
        key = normalize_name(entry["name"])
        site_by_norm.setdefault(key, []).append(entry)

    # Build slug → entry for quick lookup
    slug_to_entry: dict[str, dict] = {}
    for entry in all_site_entries:
        slug_to_entry[entry["slug"]] = entry

    # Collect existing SVG slugs on disk
    existing_svgs = set()
    for f in os.listdir(LOGOS_DIR):
        if f.endswith(".svg"):
            existing_svgs.add(f[:-4])  # strip .svg

    print(f"Existing SVG files on disk: {len(existing_svgs)}")

    # Step 2: Re-derive all logos from scratch
    print("\n=== Step 2: Re-derive all logos ===")
    changed = 0
    unchanged = 0
    downloaded_png = 0
    fallback_kept = 0
    no_match = 0

    COMMON_WORDS = {
        "calcio", "club", "united", "city", "athletic", "sport", "football",
        "real", "sporting", "nacional", "nacional", "atletico", "atletico",
        "deportivo", "olympic", "olympique", "dynamo", "dinamo", "rapid",
        "nord", "sud", "est", "ouest", "north", "south", "east", "west",
        "norte", "sur", "nord", "junior", "senior", "amateur",
    }

    def slug_shares_word(slug: str, norm_name: str) -> bool:
        """Check if slug and normalized name share a distinctive word (4+ chars,
        not a common football term)."""
        slug_words = set(w for w in slug.replace("-", " ").split()
                         if len(w) >= 4 and w not in COMMON_WORDS)
        name_words = set(w for w in norm_name.split()
                         if len(w) >= 4 and w not in COMMON_WORDS)
        return bool(slug_words & name_words)

    for team in teams:
        norm_team = normalize_name(team["name"])
        team_country = team.get("country", "") or ""

        # Find the best football-logos.cc match
        best_score = 0.0
        best_entry = None

        for norm_site, entries in site_by_norm.items():
            score = fuzzy_score(norm_team, norm_site)
            if score > best_score:
                best_score = score
                best_entry = entries[0]

        matched = False

        if best_entry and best_score >= 0.65:
            correct_slug = best_entry["slug"]

            # Slug verification: the slug must share a word with the team name
            if not slug_shares_word(correct_slug, norm_team):
                no_match += 1
                continue

            # Prefer SVG on disk
            svg_path = os.path.join(LOGOS_DIR, f"{correct_slug}.svg")
            if os.path.exists(svg_path):
                new_logo_path = f"/logos/{correct_slug}.svg"
                if team["logoPath"] != new_logo_path:
                    print(f"  FIX: {team['name']} -> {correct_slug}.svg "
                          f"(was {os.path.basename(team['logoPath'])}, "
                          f"score {best_score:.2f})")
                    team["logoPath"] = new_logo_path
                    changed += 1
                else:
                    unchanged += 1
                matched = True
            else:
                # Download PNG from football-logos.cc CDN
                content_url = best_entry.get("contentUrl", "")
                if content_url:
                    png_filename = f"{correct_slug}.png"
                    png_filepath = os.path.join(LOGOS_DIR, png_filename)
                    if not os.path.exists(png_filepath):
                        print(f"  DOWNLOAD: {team['name']} -> {png_filename} "
                              f"(score {best_score:.2f})")
                        if download_file(content_url, png_filepath):
                            downloaded_png += 1
                        else:
                            no_match += 1
                            continue
                    else:
                        downloaded_png += 1
                    new_logo_path = f"/logos/{png_filename}"
                    if team["logoPath"] != new_logo_path:
                        print(f"  FIX: {team['name']} -> {png_filename} "
                              f"(was {os.path.basename(team['logoPath'])}, "
                              f"score {best_score:.2f})")
                        team["logoPath"] = new_logo_path
                        changed += 1
                    else:
                        unchanged += 1
                    matched = True

        if not matched:
            # Keep current logo if it exists on disk
            current_path = os.path.join(PROJECT_DIR, "public", team["logoPath"].lstrip("/"))
            if os.path.exists(current_path):
                fallback_kept += 1
            else:
                # Logo file missing — try futbin if we have a numeric PNG on disk
                futbin_path = os.path.join(LOGOS_DIR, f"{team['id']}.png")
                if os.path.exists(futbin_path):
                    team["logoPath"] = f"/logos/{team['id']}.png"
                    changed += 1
                else:
                    print(f"  UNMATCHED: {team['name']}, keeping "
                          f"{os.path.basename(team['logoPath'])}")
                    no_match += 1

    # Step 3: Resolve shared logos — only one team per logo file
    print("\n=== Step 3: Resolve shared logos ===")
    logo_usage: dict[str, list[int]] = {}
    for i, t in enumerate(teams):
        lp = t["logoPath"]
        logo_usage.setdefault(lp, []).append(i)

    shared_count = 0
    resolved = 0
    for logo_path, team_indices in logo_usage.items():
        if len(team_indices) <= 1:
            continue

        shared_count += 1

        # Score each team against its logo filename using ORIGINAL names
        logo_basename = os.path.basename(logo_path).replace(".svg", "").replace(".png", "")
        logo_words = logo_basename.replace("-", " ")

        scored = []
        for idx in team_indices:
            t = teams[idx]
            # Use original name for comparison (not normalized)
            score = fuzzy_score(t["name"].lower(), logo_words)
            scored.append((score, idx))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_idx = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0

        # Only unassign if there's a clear winner (gap >= 0.15)
        if best_score - second_score < 0.15:
            continue

        # Keep the best match, unassign others
        for score, idx in scored[1:]:
            t = teams[idx]
            futbin_path = os.path.join(LOGOS_DIR, f"{t['id']}.png")
            if not os.path.exists(futbin_path):
                # Try downloading from futbin CDN
                futbin_url = f"{FUTBIN_CDN}/{t['id']}.png"
                download_file(futbin_url, futbin_path)

            if os.path.exists(futbin_path):
                print(f"  UNASSIGN: {t['name']} ({score:.2f}) from "
                      f"{os.path.basename(logo_path)} -> {t['id']}.png "
                      f"(winner: {teams[best_idx]['name']} at {best_score:.2f})")
                t["logoPath"] = f"/logos/{t['id']}.png"
                resolved += 1
            else:
                # Set to futbin path anyway — mark for later download
                print(f"  UNASSIGN: {t['name']} ({score:.2f}) from "
                      f"{os.path.basename(logo_path)} -> {t['id']}.png (pending) "
                      f"(winner: {teams[best_idx]['name']} at {best_score:.2f})")
                t["logoPath"] = f"/logos/{t['id']}.png"
                resolved += 1

    print(f"Shared logos found: {shared_count}")
    print(f"Teams unassigned: {resolved}")

    # Step 4: Write updated teams.json
    print(f"\n=== Summary ===")
    print(f"Changed:     {changed}")
    print(f"Unchanged:   {unchanged}")
    print(f"Downloaded:  {downloaded_png}")
    print(f"Fallback:    {fallback_kept}")
    print(f"No match:    {no_match}")
    print(f"Total:       {len(teams)}")

    with open(TEAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)
    print(f"\nUpdated {TEAMS_JSON}")


if __name__ == "__main__":
    main()

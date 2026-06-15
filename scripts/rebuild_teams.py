#!/usr/bin/env python3
"""
Rebuild teams.json from teams_output.csv.
- Matches CSV teams to existing teams.json entries
- Adds missing teams with logos from football-logos.cc
- Updates league/country metadata from the CSV
- Removes teams not in the CSV

Usage: python scripts/rebuild_teams.py
"""

import csv
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
CSV_FILE = os.path.join(PROJECT_DIR, "teams_output.csv")

# League ID assignment
LEAGUE_IDS = {}
_next_league_id = 1000


def get_league_id(league_name: str) -> int:
    global _next_league_id
    if league_name not in LEAGUE_IDS:
        LEAGUE_IDS[league_name] = _next_league_id
        _next_league_id += 1
    return LEAGUE_IDS[league_name]


def normalize(name: str) -> str:
    name = name.lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def country_slug(country: str) -> str:
    mapping = {
        "england": "england", "spain": "spain", "germany": "germany",
        "italy": "italy", "france": "france", "portugal": "portugal",
        "netherlands": "netherlands", "belgium": "belgium", "scotland": "scotland",
        "turkey": "turkey", "austria": "austria", "usa": "usa",
        "saudi arabia": "saudi-arabia", "brazil": "brazil", "argentina": "argentina",
        "mexico": "mexico", "norway": "norway", "sweden": "sweden",
        "denmark": "denmark", "poland": "poland", "south korea": "south-korea",
        "china": "china", "australia": "australia", "colombia": "colombia",
        "chile": "chile", "peru": "peru", "ecuador": "ecuador",
        "paraguay": "paraguay", "romania": "romania", "croatia": "croatia",
        "greece": "greece", "republic of ireland": "republic-of-ireland",
        "hungary": "hungary", "czech republic": "czech-republic",
        "ukraine": "ukraine", "india": "india", "bolivia": "bolivia",
        "venezuela": "venezuela", "haiti": "haiti", "congo dr": "congo-dr",
        "japan": "japan", "uruguay": "uruguay", "switzerland": "switzerland",
        "new zealand": "new-zealand", "wales": "wales",
        "northern ireland": "northern-ireland", "finland": "finland",
        "algeria": "algeria", "bosnia & herzegovina": "bosnia-and-herzegovina",
        "bosnia & herzegovina": "bosnia-and-herzegovina",
        "cabo verde": "cabo-verde", "curacao": "curacao",
        "curaçao": "curacao", "egypt": "egypt", "ghana": "ghana",
        "iceland": "iceland", "indonesia": "indonesia", "iran": "iran",
        "iraq": "iraq", "ivory coast": "cote-d-ivoire",
        "jordan": "jordan", "korea republic": "south-korea",
        "morocco": "morocco", "panamá": "panama", "panama": "panama",
        "qatar": "qatar", "senegal": "senegal", "south africa": "south-africa",
        "tunisia": "tunisia", "türkiye": "turkey", "turkiye": "turkey",
        "uzbekistan": "uzbekistan", "holland": "netherlands",
        "united states": "usa", "canada": "canada",
        "international": "international", "rest of world": "rest-of-world",
        "south america": "south-america", "special": "special",
        "women's league": "womens-league", "unknown": "unknown",
    }
    return mapping.get(country.lower(), country.lower().replace(" ", "-"))


def download_logo(url: str, filepath: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://football-logos.cc/",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) > 200:
                with open(filepath, "wb") as f:
                    f.write(data)
                return True
    except:
        pass
    return False


def main():
    # Load existing teams
    with open(TEAMS_JSON, "r", encoding="utf-8") as f:
        existing_teams = json.load(f)
    print(f"Loaded {len(existing_teams)} existing teams")

    # Parse CSV
    csv_entries = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_entries.append({
                "country": row["Country"].strip(),
                "league": row["League"].strip(),
                "teamType": row["Team Type"].strip(),
                "name": row["Team Name"].strip(),
            })
    print(f"CSV entries: {len(csv_entries)}")

    # Build existing team lookup (normalized name -> list of teams)
    existing_by_norm = {}
    for t in existing_teams:
        key = normalize(t["name"])
        existing_by_norm.setdefault(key, []).append(t)

    # Match CSV teams to existing teams
    # Use a pool so each existing team can only be matched once per CSV entry
    used_ids = set()
    new_teams = []
    unmatched_csv = []

    for csv_entry in csv_entries:
        csv_norm = normalize(csv_entry["name"])
        best_score = 0
        best_team = None

        # Try exact normalized match first
        if csv_norm in existing_by_norm:
            for t in existing_by_norm[csv_norm]:
                if t["id"] not in used_ids:
                    best_team = t
                    best_score = 1.0
                    break

        # Fuzzy match if no exact match
        if not best_team:
            for norm_key, team_list in existing_by_norm.items():
                score = fuzzy(csv_norm, norm_key)
                if score > best_score and score >= 0.90:
                    for t in team_list:
                        if t["id"] not in used_ids:
                            best_score = score
                            best_team = t
                            break

        if best_team:
            used_ids.add(best_team["id"])
            # Update with CSV metadata
            slug = country_slug(csv_entry["country"])
            league_id = get_league_id(csv_entry["league"])
            new_teams.append({
                "id": best_team["id"],
                "name": csv_entry["name"],
                "logoPath": best_team["logoPath"],
                "country": slug,
                "leagueId": league_id,
                "leagueName": csv_entry["league"],
            })
        else:
            unmatched_csv.append(csv_entry)

    print(f"\nMatched: {len(new_teams)}")
    print(f"Unmatched: {len(unmatched_csv)}")

    # Fetch logos for unmatched teams from football-logos.cc
    site_entries = []
    if unmatched_csv:
        print("\n=== Fetching logos for unmatched teams ===")

        # Scrape football-logos.cc
        fl_countries = [
            "england", "spain", "germany", "italy", "france", "portugal",
            "netherlands", "belgium", "scotland", "turkey", "austria",
            "usa", "saudi-arabia", "brazil", "argentina", "mexico",
            "norway", "sweden", "denmark", "poland", "south-korea", "china",
            "australia", "colombia", "chile", "peru", "ecuador", "paraguay",
            "romania", "croatia", "greece", "republic-of-ireland", "hungary",
            "czech-republic", "ukraine", "india", "bolivia", "venezuela",
            "haiti", "congo-dr", "japan", "uruguay", "switzerland", "new-zealand",
            "wales", "northern-ireland", "finland", "algeria",
            "bosnia-and-herzegovina", "cabo-verde", "curacao", "egypt",
            "ghana", "iceland", "indonesia", "iran", "iraq", "cote-d-ivoire",
            "jordan", "morocco", "panama", "qatar", "senegal", "south-africa",
            "tunisia", "uzbekistan", "canada",
            "national-teams",
        ]

        site_entries = []
        for country in fl_countries:
            url = f"https://football-logos.cc/{country}/"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except:
                continue
            pattern = re.compile(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                re.DOTALL | re.IGNORECASE,
            )
            for match in pattern.finditer(html):
                try:
                    data = json.loads(match.group(1))
                except:
                    continue
                me = data.get("mainEntity", {})
                for item in me.get("itemListElement", []):
                    u = item.get("url", "")
                    io = item.get("item", {})
                    n = io.get("name", "")
                    cu = io.get("contentUrl", "")
                    if n and u and cu:
                        slug = u.rstrip("/").split("/")[-1]
                        raw = re.sub(r"\s+logo\s*$", "", n, flags=re.IGNORECASE).strip()
                        site_entries.append({"name": raw, "slug": slug, "contentUrl": cu})
            time.sleep(0.3)

        print(f"Site entries: {len(site_entries)}")

        site_by_norm = {}
        for e in site_entries:
            site_by_norm.setdefault(normalize(e["name"]), []).append(e)

        still_missing = 0
        _next_id = 900000

        for csv_entry in unmatched_csv:
            csv_norm = normalize(csv_entry["name"])
            best_score = 0
            best_entry = None

            for ns, elist in site_by_norm.items():
                score = fuzzy(csv_norm, ns)
                if score > best_score:
                    best_score = score
                    best_entry = elist[0]

            slug = country_slug(csv_entry["country"])
            league_id = get_league_id(csv_entry["league"])

            if best_entry and best_score >= 0.60:
                logo_slug = best_entry["slug"]
                # Check for existing SVG or PNG
                svg_path = os.path.join(LOGOS_DIR, f"{logo_slug}.svg")
                png_path = os.path.join(LOGOS_DIR, f"{logo_slug}.png")

                if os.path.exists(svg_path):
                    logo_path = f"/logos/{logo_slug}.svg"
                elif os.path.exists(png_path):
                    logo_path = f"/logos/{logo_slug}.png"
                else:
                    # Download from CDN
                    if download_logo(best_entry["contentUrl"], png_path):
                        logo_path = f"/logos/{logo_slug}.png"
                        print(f"  DL: {csv_entry['name']} -> {logo_slug}.png ({best_score:.2f})")
                    else:
                        still_missing += 1
                        logo_path = f"/logos/{logo_slug}.png"
                        print(f"  FAIL: {csv_entry['name']} ({best_score:.2f})")

                _next_id += 1
                new_teams.append({
                    "id": _next_id,
                    "name": csv_entry["name"],
                    "logoPath": logo_path,
                    "country": slug,
                    "leagueId": league_id,
                    "leagueName": csv_entry["league"],
                })
            else:
                still_missing += 1
                _next_id += 1
                # Use a placeholder — the app will show a shield fallback
                name_slug = re.sub(r"[^a-z0-9]+", "-", csv_entry["name"].lower()).strip("-")
                new_teams.append({
                    "id": _next_id,
                    "name": csv_entry["name"],
                    "logoPath": f"/logos/{name_slug}.svg",
                    "country": slug,
                    "leagueId": league_id,
                    "leagueName": csv_entry["league"],
                })
                print(f"  NO MATCH: {csv_entry['name']}")

        print(f"\nStill missing logos: {still_missing}")

    # Step 4: Verify all logos and re-resolve mismatches
    print(f"\n=== Step 4: Verify and fix logos ===")

    def logo_matches_team(team_name: str, logo_path: str) -> bool:
        basename = os.path.basename(logo_path).replace(".svg", "").replace(".png", "")
        if re.match(r"^\d+$", basename):
            return True  # numeric PNGs assumed correct
        name_words = set(w for w in re.sub(r"[^a-z0-9]+", " ", team_name.lower()).split() if len(w) > 3)
        logo_words = set(w for w in basename.replace("-", " ").split() if len(w) > 3)
        return bool(name_words & logo_words)

    if not site_entries:
        # Need to scrape if we haven't already
        fl_countries = [
            "england", "spain", "germany", "italy", "france", "portugal",
            "netherlands", "belgium", "scotland", "turkey", "austria",
            "usa", "saudi-arabia", "brazil", "argentina", "mexico",
            "norway", "sweden", "denmark", "poland", "south-korea", "china",
            "australia", "colombia", "chile", "peru", "ecuador", "paraguay",
            "romania", "croatia", "greece", "republic-of-ireland", "hungary",
            "czech-republic", "ukraine", "india", "bolivia", "venezuela",
            "haiti", "congo-dr", "japan", "uruguay", "switzerland", "new-zealand",
            "wales", "northern-ireland", "finland", "algeria",
            "bosnia-and-herzegovina", "cabo-verde", "curacao", "egypt",
            "ghana", "iceland", "indonesia", "iran", "iraq", "cote-d-ivoire",
            "jordan", "morocco", "panama", "qatar", "senegal", "south-africa",
            "tunisia", "uzbekistan", "canada", "national-teams",
        ]
        for country in fl_countries:
            url = f"https://football-logos.cc/{country}/"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
            except:
                continue
            pattern = re.compile(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                re.DOTALL | re.IGNORECASE,
            )
            for match in pattern.finditer(html):
                try:
                    data = json.loads(match.group(1))
                except:
                    continue
                me = data.get("mainEntity", {})
                for item in me.get("itemListElement", []):
                    u = item.get("url", "")
                    io = item.get("item", {})
                    n = io.get("name", "")
                    cu = io.get("contentUrl", "")
                    if n and u and cu:
                        slug = u.rstrip("/").split("/")[-1]
                        raw = re.sub(r"\s+logo\s*$", "", n, flags=re.IGNORECASE).strip()
                        site_entries.append({"name": raw, "slug": slug, "contentUrl": cu})
            time.sleep(0.3)
        print(f"  Scraped {len(site_entries)} site entries")

    site_by_norm_verify = {}
    for e in site_entries:
        site_by_norm_verify.setdefault(normalize(e["name"]), []).append(e)

    fixed = 0
    for team in new_teams:
        if logo_matches_team(team["name"], team["logoPath"]):
            continue

        norm_name = normalize(team["name"])
        best_score = 0
        best_entry = None
        for ns, elist in site_by_norm_verify.items():
            score = fuzzy(norm_name, ns)
            if score > best_score:
                best_score = score
                best_entry = elist[0]

        if best_entry and best_score >= 0.60:
            logo_slug = best_entry["slug"]
            svg_path = os.path.join(LOGOS_DIR, f"{logo_slug}.svg")
            png_path = os.path.join(LOGOS_DIR, f"{logo_slug}.png")

            if os.path.exists(svg_path):
                team["logoPath"] = f"/logos/{logo_slug}.svg"
                fixed += 1
            elif os.path.exists(png_path):
                team["logoPath"] = f"/logos/{logo_slug}.png"
                fixed += 1
            else:
                if download_logo(best_entry["contentUrl"], png_path):
                    team["logoPath"] = f"/logos/{logo_slug}.png"
                    fixed += 1
                    print(f"  FIX+DL: {team['name']} -> {logo_slug}.png ({best_score:.2f})")

    print(f"  Logos re-resolved: {fixed}")

    # Write new teams.json
    print(f"\n=== Writing {len(new_teams)} teams to teams.json ===")
    with open(TEAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(new_teams, f, ensure_ascii=False, indent=2)

    # Collect referenced logo files
    referenced = set()
    for t in new_teams:
        basename = os.path.basename(t["logoPath"])
        referenced.add(basename)

    # Count orphaned logos
    all_logos = set(os.listdir(LOGOS_DIR))
    orphaned = all_logos - referenced
    print(f"\nLogo files on disk: {len(all_logos)}")
    print(f"Referenced by teams: {len(referenced)}")
    print(f"Orphaned (can delete): {len(orphaned)}")

    # Summary
    leagues = {}
    countries = {}
    for t in new_teams:
        leagues[t["leagueName"]] = leagues.get(t["leagueName"], 0) + 1
        countries[t["country"]] = countries.get(t["country"], 0) + 1

    print(f"\nLeagues ({len(leagues)}):")
    for name, count in sorted(leagues.items()):
        print(f"  {name}: {count}")

    print(f"\nDone! {len(new_teams)} teams written.")


if __name__ == "__main__":
    main()

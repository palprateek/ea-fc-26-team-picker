#!/usr/bin/env python3
"""
Fetches team-to-league mappings from football-logos.cc and updates teams.json
with leagueId and leagueName fields.

Usage:
    python scripts/add_leagues.py
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

# Wrap stdout to handle UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
TEAMS_JSON = os.path.join(PROJECT_DIR, "data", "teams.json")

# ---------------------------------------------------------------------------
# League definitions: (country_slug, league_id, league_name)
# We list multiple leagues per country where the site may differentiate them,
# but football-logos.cc typically has one page per country. We assign the top
# tier leagueId by default; second-tier teams get mapped via the second entry
# when we can distinguish them (see SECOND_TIER_LEAGUES below).
# ---------------------------------------------------------------------------
LEAGUES = [
    ("england",       13,  "English Premier League"),
    ("england",       14,  "EFL Championship"),
    ("england",       15,  "EFL League One"),
    ("england",       16,  "EFL League Two"),
    ("spain",         53,  "La Liga"),
    ("spain",         54,  "La Liga 2"),
    ("germany",       19,  "Bundesliga"),
    ("germany",       20,  "2. Bundesliga"),
    ("italy",         31,  "Serie A"),
    ("italy",         32,  "Serie B"),
    ("france",        73,  "Ligue 1"),
    ("france",        74,  "Ligue 2"),
    ("portugal",      308, "Primeira Liga"),
    ("netherlands",   10,  "Eredivisie"),
    ("belgium",       4,   "Pro League"),
    ("scotland",      50,  "Scottish Premiership"),
    ("turkey",        68,  "S\xfcper Lig"),
    ("austria",       41,  "Austrian Bundesliga"),
    ("usa",           392, "MLS"),
    ("saudi-arabia",  350, "Saudi Pro League"),
    ("brazil",        209, "Brazilian Serie A"),
    ("argentina",     215, "Primera Divisi\xf3n"),
    ("mexico",        341, "Liga MX"),
]

# Second-tier league IDs keyed by country slug.
# Teams found on the page that do NOT match a top-tier team are checked against
# the second-tier list; if the country has a second tier defined, unmatched
# teams are assigned there.
SECOND_TIER_LEAGUES = {
    "england":  (14, "EFL Championship"),
    "spain":    (54, "La Liga 2"),
    "germany":  (20, "2. Bundesliga"),
    "italy":    (32, "Serie B"),
    "france":   (74, "Ligue 2"),
}

# For countries where the site has separate pages for lower divisions we could
# add them here.  For now we treat each country page as a single list and
# assign the top-tier league.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize a team name for comparison: lowercase, strip accents, remove
    common suffixes like FC, CF, SC, de, etc."""
    # Remove "Logo" suffix from football-logos.cc names
    name = re.sub(r"\s+logo\s*$", "", name, flags=re.IGNORECASE)
    # Lowercase
    name = name.lower()
    # Strip accents / diacritics
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    # Remove common club-type words
    for suffix in [" fc", " cf", " sc", " de", " da", " do", " del", " la",
                    " le", " les", " los", " cd", " ud", " rc", " ac",
                    " as", " ss", " us", " sp", " sv", " tsv", " vfl",
                    " bsc", " fsv", " sk", " fk", " ifk", " bk",
                    " united", " city", " town", " athletic", " fc.",
                    " cf.", " sc."]:
        name = re.sub(re.escape(suffix) + r"\b", "", name)
    # Also strip leading "1. " / "2. " etc. (German convention)
    # Keep them — they are part of the identity (1. FC Koln vs FC Koln)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing dots
    name = name.rstrip(".")
    return name


def fuzzy_score(a: str, b: str) -> float:
    """Return similarity ratio between two normalized names."""
    return SequenceMatcher(None, a, b).ratio()


def fetch_jsonld_teams(url: str) -> list[str]:
    """Fetch a football-logos.cc page and extract team names from JSON-LD."""
    print(f"  Fetching {url} ...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FIFAFilterBot/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # Extract JSON-LD blocks
    team_names: list[str] = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        # Walk the JSON looking for ItemList entries
        _extract_names(data, team_names)

    # Clean up: strip "Logo" suffix for display, keep original for matching
    cleaned = []
    for n in team_names:
        n2 = re.sub(r"\s+logo\s*$", "", n, flags=re.IGNORECASE).strip()
        if n2:
            cleaned.append(n2)
    return cleaned


def _extract_names(obj, out: list[str]):
    """Recursively extract 'name' fields from JSON-LD ItemList structures."""
    if isinstance(obj, dict):
        # If this dict is a ListItem or has a "name", grab it
        if "name" in obj and isinstance(obj["name"], str):
            out.append(obj["name"])
        # Recurse into values
        for v in obj.values():
            _extract_names(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_names(item, out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Reading teams from {TEAMS_JSON}")
    with open(TEAMS_JSON, "r", encoding="utf-8") as f:
        teams = json.load(f)

    print(f"Loaded {len(teams)} teams from teams.json\n")

    # Build a lookup of normalized name -> list of team dicts
    futbin_by_norm: dict[str, list[dict]] = {}
    for t in teams:
        key = normalize_name(t["name"])
        futbin_by_norm.setdefault(key, []).append(t)

    # Track which teams have been assigned a league (by id)
    assigned: dict[int, dict] = {}

    # Deduplicate country slugs so we fetch each page only once.
    # Multiple league entries for the same country share the same page.
    seen_slugs: set[str] = set()

    for slug, league_id, league_name in LEAGUES:
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        url = f"https://football-logos.cc/{slug}/"
        try:
            site_names = fetch_jsonld_teams(url)
        except Exception as exc:
            print(f"  [WARN] Failed to fetch {url}: {exc}")
            continue

        print(f"  Found {len(site_names)} team names on page\n")

        if not site_names:
            continue

        # Determine top-tier league for this country
        top_id, top_name = league_id, league_name
        second_id, second_name = SECOND_TIER_LEAGUES.get(slug, (None, None))

        for raw_name in site_names:
            norm_site = normalize_name(raw_name)

            best_score = 0.0
            best_team = None

            for norm_futbin, team_list in futbin_by_norm.items():
                score = fuzzy_score(norm_site, norm_futbin)
                if score > best_score:
                    best_score = score
                    best_team = team_list[0]  # take first if duplicates

            if best_team and best_score >= 0.6:
                tid = best_team["id"]
                if tid not in assigned:
                    # Assign to top-tier league by default
                    assigned[tid] = {
                        "leagueId": top_id,
                        "leagueName": top_name,
                    }
                    print(f"    Matched: \"{raw_name}\" -> \"{best_team['name']}\" "
                          f"(score {best_score:.2f}) => {top_name}")
                else:
                    # Already assigned — could be second-tier match; skip
                    pass
            else:
                print(f"    No match: \"{raw_name}\" (best {best_score:.2f} "
                      f"with \"{best_team['name'] if best_team else '?'}\")")

        # Polite delay between page fetches
        time.sleep(1)

    # Apply league info to teams
    updated_count = 0
    for t in teams:
        tid = t["id"]
        if tid in assigned:
            t["leagueId"] = assigned[tid]["leagueId"]
            t["leagueName"] = assigned[tid]["leagueName"]
            updated_count += 1

    print(f"\n--- Summary ---")
    print(f"Total teams in file: {len(teams)}")
    print(f"Teams assigned a league: {updated_count}")
    print(f"Teams without league:    {len(teams) - updated_count}")

    # Write back
    with open(TEAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)

    print(f"\nUpdated {TEAMS_JSON}")


if __name__ == "__main__":
    main()

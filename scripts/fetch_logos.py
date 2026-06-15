"""
Fetch FC26 teams from futbin, match to football-logos.cc for SVG logos
and accurate league mappings, then generate data/teams.json.

Usage: python scripts/fetch_logos.py
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
from html import unescape
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdout.reconfigure(line_buffering=True)  # flush after every print

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
LOGOS_DIR = PROJECT_DIR / "public" / "logos"
DATA_DIR = PROJECT_DIR / "data"
TEAMS_JSON = DATA_DIR / "teams.json"

LOGOS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Countries we care about for FC26 leagues
LEAGUE_COUNTRIES = [
    ("england",       13,  "English Premier League"),
    ("spain",         53,  "La Liga"),
    ("germany",       19,  "Bundesliga"),
    ("italy",         31,  "Serie A"),
    ("france",        73,  "Ligue 1"),
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

# Mapping from football-logos.cc league_section headings to our league IDs
# Only includes leagues we care about (the 16 target leagues)
LEAGUE_SECTION_MAP = {
    # England
    "English Premier League": 13,
    "EFL Championship": 14,
    "EFL League One": 15,
    "EFL League Two": 16,
    # Spain
    "La Liga": 53,
    "La Liga 2": 54,
    # Germany
    "Bundesliga": 19,
    "2. Bundesliga": 20,
    # Italy
    "Serie A": 31,
    "Serie B": 32,
    # France
    "Ligue 1": 73,
    "Ligue 2": 74,
    # Portugal
    "Primeira Liga": 308,
    "Liga Portugal 2": None,
    "Liga 2": None,
    # Netherlands
    "Eredivisie": 10,
    # Belgium
    "Belgian Pro League": 4,
    "Jupiler Pro League": 4,
    "Pro League": 4,
    # Scotland
    "Scottish Premiership": 50,
    "Scottish Championship": None,
    # Turkey
    "Super Lig": 68,
    # Austria
    "Austrian Bundesliga": 41,
    "Austrian Football Bundesliga": 41,
    # USA
    "MLS": 392,
    "MLS - Major League Soccer": 392,
    # Saudi Arabia
    "Saudi Pro League": 350,
    "Saudi Professional League": 350,
    # Brazil
    "Brazilian Serie A": 209,
    "Brazilian Serie B": None,
    # Argentina
    "Argentina Primera Division": 215,
    # Mexico
    "Liga MX": 341,
}

# Normalize league_section names to canonical display names
LEAGUE_NAME_NORMALIZE = {
    "MLS - Major League Soccer": "MLS",
    "Saudi Professional League": "Saudi Pro League",
    "Austrian Football Bundesliga": "Austrian Bundesliga",
    "Argentina Primera Division": "Primera División",
    "Belgian Pro League": "Pro League",
    "Jupiler Pro League": "Pro League",
    "Super Lig": "Süper Lig",
}

# Manual overrides for well-known teams where fuzzy matching fails
# Format: futbin_name -> (leagueId, leagueName, country)
MANUAL_OVERRIDES = {
    # FC26 licensing renames
    "Milano FC": (31, "Serie A", "italy"),
    "Lombardia FC": (31, "Serie A", "italy"),
    "Milan": (31, "Serie A", "italy"),
    "Latium": (31, "Serie A", "italy"),
    "Bergamo Calcio": (31, "Serie A", "italy"),
    "Roma FC": (31, "Serie A", "italy"),
    "Napoli FC": (31, "Serie A", "italy"),

    # MLS teams that fuzzy-match to wrong countries
    "LA Galaxy": (392, "MLS", "usa"),
    "LAFC": (392, "MLS", "usa"),
    "Inter Miami CF": (392, "MLS", "usa"),
    "Seattle Sounders FC": (392, "MLS", "usa"),
    "Sporting Kansas City": (392, "MLS", "usa"),
    "Vancouver Whitecaps FC": (392, "MLS", "usa"),
    "Houston Dynamo FC": (392, "MLS", "usa"),
    "Portland Timbers": (392, "MLS", "usa"),
    "Real Salt Lake": (392, "MLS", "usa"),
    "Orlando City SC": (392, "MLS", "usa"),
    "San Jose Earthquakes": (392, "MLS", "usa"),
    "CF Montréal": (392, "MLS", "usa"),
    "Chicago Fire FC": (392, "MLS", "usa"),
    "D.C. United": (392, "MLS", "usa"),
    "New York City FC": (392, "MLS", "usa"),
    "San Diego FC": (392, "MLS", "usa"),
    "St. Louis CITY SC": (392, "MLS", "usa"),
    "Nashville SC": (392, "MLS", "usa"),
    "FC Cincinnati": (392, "MLS", "usa"),
    "Charlotte FC": (392, "MLS", "usa"),
    "Columbus Crew": (392, "MLS", "usa"),
    "FC Dallas": (392, "MLS", "usa"),
    "Austin FC": (392, "MLS", "usa"),
    "Colorado Rapids": (392, "MLS", "usa"),
    "Toronto FC": (392, "MLS", "usa"),
    "Minnesota United": (392, "MLS", "usa"),
    "Philadelphia Union": (392, "MLS", "usa"),
    "Red Bull New York": (392, "MLS", "usa"),
    "New England Revolution": (392, "MLS", "usa"),
    "Atlanta United": (392, "MLS", "usa"),

    # Portugal
    "Sporting CP": (308, "Primeira Liga", "portugal"),
    "SL Benfica": (308, "Primeira Liga", "portugal"),
    "FC Porto": (308, "Primeira Liga", "portugal"),

    # Liga MX - football-logos.cc coverage is limited, override known teams
    "Club América": (341, "Liga MX", "mexico"),
    "Guadalajara": (341, "Liga MX", "mexico"),
    "Cruz Azul": (341, "Liga MX", "mexico"),
    "Tigres UANL": (341, "Liga MX", "mexico"),
    "Pumas": (341, "Liga MX", "mexico"),
    "Club León": (341, "Liga MX", "mexico"),
    "Santos Laguna": (341, "Liga MX", "mexico"),
    "Deportivo Toluca": (341, "Liga MX", "mexico"),
    "Rayados de Monterrey": (341, "Liga MX", "mexico"),
    "Club Puebla": (341, "Liga MX", "mexico"),
    "Necaxa": (341, "Liga MX", "mexico"),
    "Mazatlán FC": (341, "Liga MX", "mexico"),
    "Atlas": (341, "Liga MX", "mexico"),
    "Club Tijuana": (341, "Liga MX", "mexico"),
    "FC Juárez": (341, "Liga MX", "mexico"),
    "Querétaro": (341, "Liga MX", "mexico"),
    "Pachuca": (341, "Liga MX", "mexico"),

    # Teams from non-target countries that fuzzy-match to wrong leagues
    # Override to correct country (no league assignment — they're not in our 16 leagues)
    "Aucas": (None, None, "ecuador"),
    "Club Atlético San Martín": (None, None, "argentina"),
    "Club Nacional": (None, None, "paraguay"),
    "FC Argeş": (None, None, "romania"),
    "U. Católica": (None, None, "chile"),
    "Universitario": (None, None, "peru"),

    # Spanish teams that fuzzy-match to Mexican slugs
    "UD Las Palmas": (145, "La Liga", "spain"),
}


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch(url, referer=None):
    """Fetch a URL with polite headers. Returns the response body as string."""
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_bytes(url, referer=None):
    """Fetch a URL and return raw bytes."""
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def normalize_name(name):
    """Normalize a team name for fuzzy matching."""
    name = re.sub(r"\s+logo\s*$", "", name, flags=re.IGNORECASE)
    name = name.lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    for suffix in [" fc", " cf", " sc", " de", " da", " do", " del", " la",
                    " le", " les", " los", " cd", " ud", " rc", " ac",
                    " as", " ss", " us", " sp", " sv", " tsv", " vfl",
                    " bsc", " fsv", " sk", " fk", " ifk", " bk",
                    " united", " city", " town", " athletic", " fc.",
                    " cf.", " sc."]:
        name = re.sub(re.escape(suffix) + r"\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(".")
    return name


def fuzzy_score(a, b):
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Step 1: Fetch FC26 team list from futbin
# ---------------------------------------------------------------------------

def fetch_futbin_teams():
    """Scrape futbin.com/clubs for the FC26 team list."""
    log("=" * 60)
    log("STEP 1: Fetching FC26 teams from futbin.com")
    log("=" * 60)

    log("  Fetching https://www.futbin.com/clubs ...")
    t0 = time.time()
    html = fetch("https://www.futbin.com/clubs")
    log(f"  Fetched in {time.time()-t0:.1f}s, {len(html)} bytes")

    # Parse club entries
    link_pattern = r'<a[^>]*href="/26/clubs/(\d+)/[^"]*"[^>]*>\s*([^<]+?)\s*</a>'
    img_pattern = r'<img[^>]*src="(https://cdn3\.futbin\.com/content/fifa26/img/clubs/dark/(\d+)\.png[^"]*)"'

    log("  Parsing HTML for club links...")
    link_matches = re.findall(link_pattern, html)
    log(f"  Found {len(link_matches)} club link matches")

    log("  Parsing HTML for club images...")
    img_matches = re.findall(img_pattern, html)
    log(f"  Found {len(img_matches)} club image matches")

    id_to_name = {}
    for club_id, name in link_matches:
        if club_id not in id_to_name:
            id_to_name[club_id] = unescape(name).strip()

    teams = []
    seen_ids = set()
    for full_url, club_id in img_matches:
        if club_id in seen_ids:
            continue
        seen_ids.add(club_id)
        name = id_to_name.get(club_id, f"Club {club_id}")
        teams.append({"id": int(club_id), "name": name})

    log(f"  Total unique clubs from futbin: {len(teams)}")
    return teams


def filter_fc26_teams(futbin_teams):
    """Filter futbin teams to only FC26 playable clubs."""
    log("\nFiltering to FC26 playable clubs...")

    national_patterns = [
        r"^(Australia|Brazil|Colombia|Croatia|Ecuador|Egypt|Ghana|Mexico|Netherlands|"
        r"Panama|Paraguay|Qatar|South Korea|Tunisia|Uruguay)$",
    ]

    filtered = []
    removed_national = 0
    for t in futbin_teams:
        name = t["name"]
        is_national = any(re.match(p, name, re.IGNORECASE) for p in national_patterns)
        if is_national:
            removed_national += 1
            continue
        filtered.append(t)

    log(f"  Removed {removed_national} national teams")

    seen_names = {}
    deduped = []
    removed_dupes = 0
    for t in filtered:
        norm = normalize_name(t["name"])
        if norm not in seen_names:
            seen_names[norm] = t
            deduped.append(t)
        else:
            removed_dupes += 1

    log(f"  Removed {removed_dupes} duplicate entries")
    log(f"  FC26 teams remaining: {len(deduped)}")
    return deduped


# ---------------------------------------------------------------------------
# Step 2: Scrape football-logos.cc country pages
# ---------------------------------------------------------------------------

def scrape_country_page(country_slug):
    """Scrape a football-logos.cc country page for team slugs and PNG hashes."""
    url = f"https://football-logos.cc/{country_slug}/"
    log(f"    Fetching {url} ...")

    try:
        t0 = time.time()
        html = fetch(url)
        log(f"    Fetched in {time.time()-t0:.1f}s, {len(html)} bytes")
    except Exception as e:
        log(f"    [WARN] Failed to fetch {url}: {e}")
        return []

    teams = []

    img_pattern = re.compile(
        r'<img[^>]*src="https://assets\.football-logos\.cc/logos/'
        + re.escape(country_slug)
        + r'/256x256/([^.]+)\.([a-f0-9]+)\.png[^"]*"'
    )

    img_matches = list(img_pattern.finditer(html))
    log(f"    Found {len(img_matches)} image tags matching pattern")

    # Pre-extract all headings with positions for faster lookup
    headings = []
    for m in re.finditer(r'<h[23][^>]*>([^<]+)</h[23]>', html):
        headings.append((m.start(), unescape(m.group(1)).strip()))

    for match in img_matches:
        slug = match.group(1)
        png_hash = match.group(2)
        pos = match.start()

        current_league = None
        for h_pos, h_text in headings:
            if h_pos < pos:
                if any(kw in h_text.lower() for kw in [
                    "league", "liga", "bundesliga", "serie", "ligue",
                    "premier", "championship", "division", "primeira",
                    "eredivisie", "pro league", "super", "scottish",
                    "mls"
                ]):
                    current_league = h_text
            else:
                break

        teams.append({
            "slug": slug,
            "png_hash": png_hash,
            "league_section": current_league,
        })

    log(f"    Extracted {len(teams)} team entries")
    return teams


def scrape_all_countries():
    """Scrape all league country pages."""
    log("\n" + "=" * 60)
    log("STEP 2: Scraping football-logos.cc country pages")
    log("=" * 60)

    all_teams = {}
    total_countries = len(LEAGUE_COUNTRIES)

    for idx, (country_slug, league_id, league_name) in enumerate(LEAGUE_COUNTRIES):
        log(f"\n  [{idx+1}/{total_countries}] {country_slug} ({league_name})")
        teams = scrape_country_page(country_slug)
        new_count = 0
        for t in teams:
            if t["slug"] not in all_teams:
                all_teams[t["slug"]] = {
                    **t,
                    "country": country_slug,
                    "country_league_id": league_id,
                    "country_league_name": league_name,
                }
                new_count += 1
        log(f"    Added {new_count} new slugs ({len(all_teams)} total unique)")
        time.sleep(1)

    log(f"\nTotal unique team slugs from football-logos.cc: {len(all_teams)}")
    return all_teams


# ---------------------------------------------------------------------------
# Step 3: Match FC26 teams to football-logos.cc
# ---------------------------------------------------------------------------

def match_teams(futbin_teams, flcc_teams):
    """Match futbin FC26 teams to football-logos.cc entries via fuzzy matching.
    
    Uses country-aware matching: prefers same-country matches to prevent
    cross-country errors (e.g., LA Galaxy matching to a Spanish team).
    """
    log("\n" + "=" * 60)
    log("STEP 3: Matching FC26 teams to football-logos.cc")
    log("=" * 60)

    # Build normalized lookup grouped by country
    log("  Building flcc normalized lookup (by country)...")
    flcc_by_country_norm = {}  # country -> {norm: [entries]}
    for slug, t in flcc_teams.items():
        norm = normalize_name(slug.replace("-", " "))
        country = t["country"]
        flcc_by_country_norm.setdefault(country, {}).setdefault(norm, []).append(t)
    
    # Also build a flat lookup for cross-country fallback
    flcc_by_norm = {}
    for slug, t in flcc_teams.items():
        norm = normalize_name(slug.replace("-", " "))
        flcc_by_norm.setdefault(norm, []).append(t)
    
    log(f"  flcc unique normalized keys: {len(flcc_by_norm)}")
    log(f"  flcc countries: {len(flcc_by_country_norm)}")

    matched = []
    unmatched = []
    used_slugs = set()
    total = len(futbin_teams)
    t0 = time.time()

    for idx, ft in enumerate(futbin_teams):
        norm_futbin = normalize_name(ft["name"])

        # Phase 1: Find best match WITHIN each country
        # If a good match exists in any country, use it (prefer exact/near-exact)
        best_same_country_score = 0.0
        best_same_country_match = None

        for country, country_norms in flcc_by_country_norm.items():
            for norm_flcc, entries in country_norms.items():
                score = fuzzy_score(norm_futbin, norm_flcc)
                if score > best_same_country_score:
                    best_same_country_score = score
                    best_same_country_match = entries[0]

        # Phase 2: Find best cross-country match (only if no good same-country match)
        best_cross_score = 0.0
        best_cross_match = None

        if best_same_country_score < 0.85:
            # No strong same-country match — check cross-country
            for norm_flcc, entries in flcc_by_norm.items():
                score = fuzzy_score(norm_futbin, norm_flcc)
                if score > best_cross_score:
                    best_cross_score = score
                    best_cross_match = entries[0]

        # Decision: use same-country if it's good (>=0.55), otherwise try cross-country
        if best_same_country_match and best_same_country_score >= 0.55:
            best_match = best_same_country_match
            best_score = best_same_country_score
        elif best_cross_match and best_cross_score >= 0.75:
            # Higher threshold for cross-country matches to prevent wrong-country errors
            best_match = best_cross_match
            best_score = best_cross_score
        else:
            best_match = None
            best_score = 0.0

        if best_match:
            slug = best_match["slug"]
            if slug in used_slugs:
                # Slug already taken — try next best match
                best_match = None
                best_score = 0.0
                for norm_flcc, entries in flcc_by_norm.items():
                    score = fuzzy_score(norm_futbin, norm_flcc)
                    if score > best_score and entries[0]["slug"] not in used_slugs:
                        best_score = score
                        best_match = entries[0]

            if best_match and best_score >= 0.55:
                used_slugs.add(best_match["slug"])
                matched.append({
                    "id": ft["id"],
                    "name": ft["name"],
                    "slug": best_match["slug"],
                    "country": best_match["country"],
                    "league_id": best_match["country_league_id"],
                    "league_name": best_match["country_league_name"],
                    "league_section": best_match.get("league_section"),
                    "score": best_score,
                })
            else:
                unmatched.append(ft)
        else:
            unmatched.append(ft)

        if (idx + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            log(f"  Matching progress: {idx+1}/{total} "
                f"({len(matched)} matched, {len(unmatched)} unmatched) "
                f"[{rate:.0f} teams/s, {elapsed:.1f}s elapsed]")

    elapsed = time.time() - t0
    log(f"\n  Matching complete in {elapsed:.1f}s")
    log(f"  Matched: {len(matched)} teams")
    log(f"  Unmatched: {len(unmatched)} teams")
    if unmatched:
        log(f"  Sample unmatched: {[t['name'] for t in unmatched[:10]]}")

    return matched, unmatched


# ---------------------------------------------------------------------------
# Step 4: Fetch SVG hashes and download SVGs
# ---------------------------------------------------------------------------

def fetch_svg_hash(country, slug):
    """Visit a team's detail page on football-logos.cc and extract the SVG hash."""
    url = f"https://football-logos.cc/{country}/{slug}/"
    try:
        html = fetch(url, referer="https://football-logos.cc/")
    except Exception as e:
        log(f"      [WARN] Failed to fetch {url}: {e}")
        return None

    match = re.search(r'data-svg-hash="([a-f0-9]+)"', html)
    if match:
        return match.group(1)

    match = re.search(r'https://images\.football-logos\.cc/[^"]+\.([a-f0-9]+)\.svg', html)
    if match:
        return match.group(1)

    return None


def download_svg(country, slug, svg_hash):
    """Download an SVG logo from football-logos.cc."""
    filepath = LOGOS_DIR / f"{slug}.svg"
    if filepath.exists() and filepath.stat().st_size > 100:
        log(f"      Already exists: {slug}.svg")
        return True

    url = f"https://images.football-logos.cc/{country}/{slug}.{svg_hash}.svg"
    try:
        data = fetch_bytes(url, referer="https://football-logos.cc/")
        if len(data) > 100:
            filepath.write_bytes(data)
            return True
        else:
            log(f"      Too small ({len(data)}B): {slug}")
    except Exception as e:
        log(f"      Failed download: {slug} — {e}")
    return False


def download_all_svgs(matched_teams):
    """Download SVGs for all matched teams."""
    log("\n" + "=" * 60)
    log("STEP 4: Downloading SVG logos")
    log("=" * 60)

    # Skip teams that already have SVGs downloaded
    already_done = 0
    to_download = []
    for team in matched_teams:
        svg_path = LOGOS_DIR / f"{team['slug']}.svg"
        if svg_path.exists() and svg_path.stat().st_size > 100:
            already_done += 1
        else:
            to_download.append(team)

    # Add Liga MX teams not in futbin
    LIGA_MX_SLUGS = [
        ("cd-guadalajara", "mexico"), ("cruz-azul", "mexico"), ("tigres-uanl", "mexico"),
        ("club-leon", "mexico"), ("santos-laguna", "mexico"), ("monterrey", "mexico"),
        ("puebla", "mexico"), ("necaxa", "mexico"), ("mazatlan-fc", "mexico"),
        ("atlas", "mexico"), ("club-tijuana", "mexico"),
    ]
    for slug, country in LIGA_MX_SLUGS:
        svg_path = LOGOS_DIR / f"{slug}.svg"
        if not svg_path.exists() or svg_path.stat().st_size <= 100:
            to_download.append({"name": slug, "slug": slug, "country": country})

    log(f"  Already downloaded: {already_done}")
    log(f"  Remaining to download: {len(to_download)}")

    success = already_done
    fail = 0
    total = len(to_download)
    t0 = time.time()

    for i, team in enumerate(to_download):
        slug = team["slug"]
        country = team["country"]

        log(f"  [{i+1}/{total}] {team['name']} ({country}/{slug})")

        # Fetch SVG hash from team detail page
        log(f"      Fetching page for SVG hash...")
        svg_hash = fetch_svg_hash(country, slug)
        if not svg_hash:
            log(f"      No SVG hash found!")
            fail += 1
            time.sleep(0.3)
            continue

        log(f"      SVG hash: {svg_hash}")

        # Download SVG
        if download_svg(country, slug, svg_hash):
            success += 1
            log(f"      OK")
        else:
            fail += 1

        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            log(f"\n  --- Progress: {i+1}/{total} "
                f"({success} ok, {fail} failed) "
                f"[{rate:.1f} teams/s, ETA {eta:.0f}s] ---\n")

        time.sleep(0.3)

    elapsed = time.time() - t0
    log(f"\nSVG download complete in {elapsed:.1f}s: {success} succeeded, {fail} failed")
    return success


# ---------------------------------------------------------------------------
# Step 5: Generate teams.json
# ---------------------------------------------------------------------------

def generate_teams_json(matched_teams, unmatched_teams):
    """Generate the final data/teams.json."""
    log("\n" + "=" * 60)
    log("STEP 5: Generating teams.json")
    log("=" * 60)

    teams = []

    for t in matched_teams:
        svg_path = LOGOS_DIR / f"{t['slug']}.svg"
        if svg_path.exists() and svg_path.stat().st_size > 100:
            # Check manual overrides first
            if t["name"] in MANUAL_OVERRIDES:
                league_id, league_name, country = MANUAL_OVERRIDES[t["name"]]
                entry = {
                    "id": t["id"],
                    "name": t["name"],
                    "logoPath": f"/logos/{t['slug']}.svg",
                    "leagueId": league_id,
                    "leagueName": league_name,
                    "country": country,
                }
                teams.append(entry)
                continue

            # Use league_section to get the correct league ID when available
            league_section = t.get("league_section")
            if league_section and league_section in LEAGUE_SECTION_MAP:
                mapped_id = LEAGUE_SECTION_MAP[league_section]
                if mapped_id is not None:
                    league_id = mapped_id
                    league_name = LEAGUE_NAME_NORMALIZE.get(league_section, league_section)
                else:
                    # Section exists but not in our target leagues (e.g. Serie C, League One)
                    # Don't assign to country default — leave without league
                    league_id = None
                    league_name = None
            elif league_section:
                # Has a league_section but we don't recognize it
                # Don't assign to country default
                league_id = None
                league_name = None
            else:
                # No league_section info — use country default
                league_id = t["league_id"]
                league_name = t["league_name"]

            entry = {
                "id": t["id"],
                "name": t["name"],
                "logoPath": f"/logos/{t['slug']}.svg",
                "country": t["country"],
            }
            if league_id is not None:
                entry["leagueId"] = league_id
                entry["leagueName"] = league_name
            teams.append(entry)

    for t in unmatched_teams:
        # Check manual overrides first
        if t["name"] in MANUAL_OVERRIDES:
            league_id, league_name, country = MANUAL_OVERRIDES[t["name"]]
            # Try to find an SVG logo for this team
            slug = t["name"].lower().replace(" ", "-").replace("é", "e").replace("á", "a").replace("ó", "o").replace("ú", "u").replace("ñ", "n").replace("ü", "u")
            slug = re.sub(r"[^a-z0-9-]", "", slug)
            svg_path = LOGOS_DIR / f"{slug}.svg"
            if svg_path.exists() and svg_path.stat().st_size > 100:
                entry = {
                    "id": t["id"],
                    "name": t["name"],
                    "logoPath": f"/logos/{slug}.svg",
                    "country": country,
                }
                if league_id is not None:
                    entry["leagueId"] = league_id
                    entry["leagueName"] = league_name
                teams.append(entry)
                continue
            # Fall through to PNG check

        png_path = LOGOS_DIR / f"{t['id']}.png"
        if png_path.exists() and png_path.stat().st_size > 100:
            entry = {
                "id": t["id"],
                "name": t["name"],
                "logoPath": f"/logos/{t['id']}.png",
            }
            teams.append(entry)

    # Add Liga MX teams not in futbin
    LIGA_MX_TEAMS = [
        ("Club América", "club-america"),
        ("Guadalajara", "cd-guadalajara"),
        ("Cruz Azul", "cruz-azul"),
        ("Tigres UANL", "tigres-uanl"),
        ("Pumas UNAM", "unam-pumas"),
        ("Club León", "club-leon"),
        ("Santos Laguna", "santos-laguna"),
        ("Deportivo Toluca", "toluca"),
        ("Monterrey", "monterrey"),
        ("Club Puebla", "puebla"),
        ("Necaxa", "necaxa"),
        ("Mazatlán FC", "mazatlan-fc"),
        ("Atlas", "atlas"),
        ("Club Tijuana", "club-tijuana"),
        ("FC Juárez", "fc-juarez"),
        ("Querétaro", "queretaro-fc"),
        ("Pachuca", "pachuca"),
        ("San Luis", "atletico-de-san-luis"),
    ]
    existing_names = {t["name"] for t in teams}
    for name, slug in LIGA_MX_TEAMS:
        if name not in existing_names:
            svg_path = LOGOS_DIR / f"{slug}.svg"
            if svg_path.exists() and svg_path.stat().st_size > 100:
                teams.append({
                    "id": 90000 + hash(slug) % 10000,
                    "name": name,
                    "logoPath": f"/logos/{slug}.svg",
                    "leagueId": 341,
                    "leagueName": "Liga MX",
                    "country": "mexico",
                })

    teams.sort(key=lambda t: t["name"])

    with open(TEAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)

    log(f"Wrote {len(teams)} teams to {TEAMS_JSON}")

    with_svg = sum(1 for t in teams if t["logoPath"].endswith(".svg"))
    with_league = sum(1 for t in teams if "leagueId" in t)
    log(f"  With SVG logos: {with_svg}")
    log(f"  With league mapping: {with_league}")
    log(f"  Without league: {len(teams) - with_league}")

    return teams


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t_start = time.time()
    skip_downloads = "--skip-downloads" in sys.argv
    log("Starting fetch_logos.py")
    log(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if skip_downloads:
        log("  [SKIP DOWNLOADS mode — SVG downloads will be skipped]")

    # Step 1
    futbin_teams = fetch_futbin_teams()
    fc26_teams = filter_fc26_teams(futbin_teams)

    # Step 2
    flcc_teams = scrape_all_countries()

    # Step 3
    matched, unmatched = match_teams(fc26_teams, flcc_teams)

    # Step 4
    if not skip_downloads:
        download_all_svgs(matched)
    else:
        log("\n" + "=" * 60)
        log("STEP 4: Skipping SVG downloads (--skip-downloads)")
        log("=" * 60)

    # Step 5
    generate_teams_json(matched, unmatched)

    total_time = time.time() - t_start
    log("\n" + "=" * 60)
    log(f"DONE — Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    log("=" * 60)


if __name__ == "__main__":
    main()

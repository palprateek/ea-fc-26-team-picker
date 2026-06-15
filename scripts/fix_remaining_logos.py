#!/usr/bin/env python3
"""
Fix remaining wrong/missing team logos using:
- fclogo.top for national teams (2026 FIFA World Cup pack)
- football-logos.cc for remaining club teams
"""
import io, json, os, re, sys, time, urllib.request, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
TEAMS_JSON = os.path.join(PROJECT_DIR, "data", "teams.json")
LOGOS_DIR = os.path.join(PROJECT_DIR, "public", "logos")

NATIONAL_LOGOS = {
    "Australia": "https://cdn.sanity.io/images/11hmdf08/production/989b9c595562cfa0a71b57b9f3ab057c2fee0c23-800x800.png",
    "Iran": "https://cdn.sanity.io/images/11hmdf08/production/88185765b47ec7c596cb9aad655962717c298988-800x800.png",
    "Japan": "https://cdn.sanity.io/images/11hmdf08/production/a4b2800d80b70e06caa0f6b55d7bc5bad21a8bf6-800x800.png",
    "Jordan": "https://cdn.sanity.io/images/11hmdf08/production/1f3c4240db51f6af504e97e041a15475811a6b54-800x800.png",
    "Qatar": "https://cdn.sanity.io/images/11hmdf08/production/676011400bab38520c7681a9879211eb6fdff23f-800x800.png",
    "Saudi Arabia": "https://cdn.sanity.io/images/11hmdf08/production/2bcbf4a6e753be74d28257edce0244ca01a2240f-800x800.png",
    "Korea Republic": "https://cdn.sanity.io/images/11hmdf08/production/bb2c3a88bc407896eb036e8ed97327ace26cc046-800x800.png",
    "Uzbekistan": "https://cdn.sanity.io/images/11hmdf08/production/cbece8b5563fcfe492a8bf76fbb100a7b985e014-800x800.png",
    "Canada": "https://cdn.sanity.io/images/11hmdf08/production/361e31586c2f420186cfcaea4fdbee517cd4e4b1-800x800.png",
    "United States": "https://cdn.sanity.io/images/11hmdf08/production/abd1754b80ea91859a704867c45107aa3fea8356-800x800.png",
    "Mexico": "https://cdn.sanity.io/images/11hmdf08/production/8981e995b8b94fd54050a901c910b3152af3d948-800x800.png",
    "Cura\u00e7ao": "https://cdn.sanity.io/images/11hmdf08/production/06d5315cead5906f0df28977f86a0b05c644ceef-800x800.png",
    "Panam\u00e1": "https://cdn.sanity.io/images/11hmdf08/production/cc9b675573b314497a97a54c8e173a41936ace39-800x800.png",
    "Algeria": "https://cdn.sanity.io/images/11hmdf08/production/1cd689605a3059d2d372573468e5f0d52247c3f8-800x800.png",
    "Cabo Verde": "https://cdn.sanity.io/images/11hmdf08/production/ca1f11416e8a7e967886fba90864a39924899413-800x800.png",
    "Egypt": "https://cdn.sanity.io/images/11hmdf08/production/4454f249f22ebe2b9953c71dcf85f3430c18489b-800x800.png",
    "Ghana": "https://cdn.sanity.io/images/11hmdf08/production/009f4ad8a911c6445dd882853004ea16010b7ccb-800x800.png",
    "Morocco": "https://cdn.sanity.io/images/11hmdf08/production/e747015e806e03ae3e6227eea3033445bae48eb0-800x800.png",
    "Senegal": "https://cdn.sanity.io/images/11hmdf08/production/b3efa4d53601825dfd5113738262829c446cf338-800x800.png",
    "South Africa": "https://cdn.sanity.io/images/11hmdf08/production/bdcc2e2e2d06c7d06627cb0c9ced82967ad53540-800x800.png",
    "Tunisia": "https://cdn.sanity.io/images/11hmdf08/production/195d9aa20ea237c4699dd0b7b0c33537e549de42-800x800.png",
    "Argentina": "https://cdn.sanity.io/images/11hmdf08/production/f04dd86bc10f33081427aa44249ac0571656efe4-800x800.png",
    "Brazil": "https://cdn.sanity.io/images/11hmdf08/production/23b6f30fe7970787d338ce5500af28a87eff2d98-800x800.png",
    "Colombia": "https://cdn.sanity.io/images/11hmdf08/production/bb6d3ffb3655a4e576ca89ff06fa2b096a3f271a-800x800.png",
    "Ecuador": "https://cdn.sanity.io/images/11hmdf08/production/a965bda16e4bd797dfdf0f794477786161332bf3-800x800.png",
    "Paraguay": "https://cdn.sanity.io/images/11hmdf08/production/1d19e3b53768326defb6308bc5d26b61967224c5-800x800.png",
    "Uruguay": "https://cdn.sanity.io/images/11hmdf08/production/fc4d53800c30b5037332ee95d349e1c58305d7b3-800x800.png",
    "New Zealand": "https://cdn.sanity.io/images/11hmdf08/production/8f781fadf5bed1dc5a5efa9e19b5fd022eb69ec8-800x800.png",
    "Austria": "https://cdn.sanity.io/images/11hmdf08/production/a89bae9320c790d3eebefafb1c538f9e044f9db4-800x800.png",
    "Belgium": "https://cdn.sanity.io/images/11hmdf08/production/5ba1a121b26094111f55c244c2aeb291b453042c-800x800.png",
    "Bosnia & Herzegovina": "https://cdn.sanity.io/images/11hmdf08/production/4065cc66e54e5cfdfdb12de6b0b48775e161c3bd-800x800.png",
    "Croatia": "https://cdn.sanity.io/images/11hmdf08/production/e9a527e6d3f85015abeb1f7c4a9069667ffc1ad0-800x800.png",
    "Czech Republic": "https://cdn.sanity.io/images/11hmdf08/production/7fbe1281ea75118a0c940d9d1d1043b49afa7199-800x800.png",
    "England": "https://cdn.sanity.io/images/11hmdf08/production/bc89320e50af84fe675f506c8b0f2e5fd8d04be6-800x800.png",
    "France": "https://cdn.sanity.io/images/11hmdf08/production/94a93f99ab960b2aa0aa642cf3e8a911ac8ffde5-800x800.png",
    "Germany": "https://cdn.sanity.io/images/11hmdf08/production/2ac6e12b67f767f9afcd2bc54ee1590e7d41c509-800x800.png",
    "Holland": "https://cdn.sanity.io/images/11hmdf08/production/23f36084302ca7b8ffccd10d9f268db4105fcd71-800x800.png",
    "Hungary": "https://cdn.sanity.io/images/11hmdf08/production/9c84ac975fcfa855f618bdb9ac6c184af5271523-800x800.png",
    "Norway": "https://cdn.sanity.io/images/11hmdf08/production/a2bfb9751943b70c86ab4660f1aef2e60cee17cd-800x800.png",
    "Portugal": "https://cdn.sanity.io/images/11hmdf08/production/9c84ac975fcfa855f618bdb9ac6c184af5271523-800x800.png",
    "Scotland": "https://cdn.sanity.io/images/11hmdf08/production/4440f00cec09f5debfe184a129406ea70dcc4511-800x800.png",
    "Spain": "https://cdn.sanity.io/images/11hmdf08/production/c0bb5c152a8bc1e7f19a020dc3ab66294eda611e-800x800.png",
    "Sweden": "https://cdn.sanity.io/images/11hmdf08/production/57258e447a5261842d230470482a79ec75ff1728-800x800.png",
    "Switzerland": "https://cdn.sanity.io/images/11hmdf08/production/ffd4aa1e0cc71473a9e381d530c7b8ab2773d43f-800x800.png",
    "T\u00fcrkiye": "https://cdn.sanity.io/images/11hmdf08/production/4e4d8744fe5b8caac3177af72de3d96fba24327e-800x800.png",
    "Haiti": "https://cdn.sanity.io/images/11hmdf08/production/f04f47abd36b1e3ae533da0c367032d8ccefee7f-800x800.png",
    "Congo DR": "https://cdn.sanity.io/images/11hmdf08/production/9f1e34d803cc270061224e8f4f8d8f7cfc8deb36-800x800.png",
    "Iraq": "https://cdn.sanity.io/images/11hmdf08/production/29d33e735f4cc2c3afac1490cea50a5d176bf47b-800x800.png",
    "Ivory Coast": "https://cdn.sanity.io/images/11hmdf08/production/ccf5311072ea76e8310a06a3f436d3821a76d349-800x800.png",
    "Finland": "https://cdn.sanity.io/images/11hmdf08/production/8f781fadf5bed1dc5a5efa9e19b5fd022eb69ec8-800x800.png",
    "Wales": "https://cdn.sanity.io/images/11hmdf08/production/bc89320e50af84fe675f506c8b0f2e5fd8d04be6-800x800.png",
    "Northern Ireland": "https://cdn.sanity.io/images/11hmdf08/production/4440f00cec09f5debfe184a129406ea70dcc4511-800x800.png",
    "Republic of Ireland": "https://cdn.sanity.io/images/11hmdf08/production/4440f00cec09f5debfe184a129406ea70dcc4511-800x800.png",
    "Denmark": "https://cdn.sanity.io/images/11hmdf08/production/a2bfb9751943b70c86ab4660f1aef2e60cee17cd-800x800.png",
    "Poland": "https://cdn.sanity.io/images/11hmdf08/production/7fbe1281ea75118a0c940d9d1d1043b49afa7199-800x800.png",
    "Romania": "https://cdn.sanity.io/images/11hmdf08/production/e9a527e6d3f85015abeb1f7c4a9069667ffc1ad0-800x800.png",
    "Ukraine": "https://cdn.sanity.io/images/11hmdf08/production/4e4d8744fe5b8caac3177af72de3d96fba24327e-800x800.png",
    "Indonesia": "https://cdn.sanity.io/images/11hmdf08/production/29d33e735f4cc2c3afac1490cea50a5d176bf47b-800x800.png",
    "Iceland": "https://cdn.sanity.io/images/11hmdf08/production/57258e447a5261842d230470482a79ec75ff1728-800x800.png",
}

# Add women's national teams (reuse men's logos)
for country in list(NATIONAL_LOGOS.keys()):
    NATIONAL_LOGOS[f"{country} Women"] = NATIONAL_LOGOS[country]


def download(url, filepath):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) > 200:
                with open(filepath, "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"  FAIL download: {e}")
    return False


def main():
    teams = json.load(open(TEAMS_JSON, "r", encoding="utf-8"))
    print(f"Loaded {len(teams)} teams")

    fixed = 0

    # Step 1: Fix national team logos from fclogo.top
    print("\n=== Fixing national team logos ===")
    for t in teams:
        if t["name"] not in NATIONAL_LOGOS:
            continue

        slug = re.sub(r"[^a-z0-9]+", "-", t["name"].lower()).strip("-")
        slug = slug.replace("\u00e7", "c").replace("\u00fc", "u").replace("\u00f6", "o").replace("\u00e1", "a")
        png_path = os.path.join(LOGOS_DIR, f"{slug}.png")

        if not os.path.exists(png_path):
            url = NATIONAL_LOGOS[t["name"]]
            if download(url, png_path):
                print(f"  DL: {t['name']} -> {slug}.png")
            else:
                continue

        old = t["logoPath"]
        t["logoPath"] = f"/logos/{slug}.png"
        if old != t["logoPath"]:
            print(f"  FIX: {t['name']} -> {slug}.png (was {os.path.basename(old)})")
        fixed += 1

    print(f"\nNational teams fixed: {fixed}")

    # Step 2: Fix remaining wrong club team logos via football-logos.cc
    print("\n=== Fixing remaining club team logos ===")
    # Scrape football-logos.cc for additional pages
    extra_pages = [
        "https://football-logos.cc/national-teams/",
        "https://football-logos.cc/tournaments/uefa-womens-champions-league/",
        "https://football-logos.cc/tournaments/uefa-euro-2024/",
        "https://football-logos.cc/tournaments/fifa-world-cup-2022/",
        "https://football-logos.cc/tournaments/uefa-euro-2020/",
        "https://football-logos.cc/tournaments/copa-america-2024/",
    ]

    site_entries = []
    for url in extra_pages:
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
                io_obj = item.get("item", {})
                n = io_obj.get("name", "")
                cu = io_obj.get("contentUrl", "")
                if n and u and cu:
                    slug = u.rstrip("/").split("/")[-1]
                    raw = re.sub(r"\s+logo\s*$", "", n, flags=re.IGNORECASE).strip()
                    site_entries.append({"name": raw, "slug": slug, "contentUrl": cu})
        time.sleep(0.5)

    print(f"Extra site entries: {len(site_entries)}")

    def normalize(name):
        name = name.lower()
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]", "", name)

    def fuzzy(a, b):
        return SequenceMatcher(None, a, b).ratio()

    site_by_norm = {}
    for e in site_entries:
        site_by_norm.setdefault(normalize(e["name"]), []).append(e)

    club_fixed = 0
    for t in teams:
        # Check if current logo matches team name
        basename = os.path.basename(t["logoPath"]).replace(".svg", "").replace(".png", "")
        if re.match(r"^\d+$", basename):
            continue
        name_words = set(w for w in re.sub(r"[^a-z0-9]+", " ", t["name"].lower()).split() if len(w) > 3)
        logo_words = set(w for w in basename.replace("-", " ").split() if len(w) > 3)
        if name_words & logo_words:
            continue  # Already correct

        # Try to find better match from extra pages
        norm = normalize(t["name"])
        best_score = 0
        best_entry = None
        for ns, elist in site_by_norm.items():
            score = fuzzy(norm, ns)
            if score > best_score:
                best_score = score
                best_entry = elist[0]

        if best_entry and best_score >= 0.70:
            logo_slug = best_entry["slug"]
            png_path = os.path.join(LOGOS_DIR, f"{logo_slug}.png")
            svg_path = os.path.join(LOGOS_DIR, f"{logo_slug}.svg")

            if os.path.exists(svg_path):
                t["logoPath"] = f"/logos/{logo_slug}.svg"
                club_fixed += 1
                print(f"  FIX: {t['name']} -> {logo_slug}.svg ({best_score:.2f})")
            elif os.path.exists(png_path):
                t["logoPath"] = f"/logos/{logo_slug}.png"
                club_fixed += 1
                print(f"  FIX: {t['name']} -> {logo_slug}.png ({best_score:.2f})")
            elif download(best_entry["contentUrl"], png_path):
                t["logoPath"] = f"/logos/{logo_slug}.png"
                club_fixed += 1
                print(f"  FIX+DL: {t['name']} -> {logo_slug}.png ({best_score:.2f})")

    print(f"\nClub teams fixed from extra pages: {club_fixed}")

    # Save
    with open(TEAMS_JSON, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {TEAMS_JSON}")
    print(f"Total fixed: {fixed + club_fixed}")


if __name__ == "__main__":
    main()

# EA FC Team Picker

> **Live:** <https://PROJECT.vercel.app> 

A browser-based AR filter that randomly assigns EA FC clubs to players via the device camera. Point the camera at 1–2 faces, tap **SPIN**, and a slot-machine reel flashes team crests before landing on a random assignment above each player's head.

Used for FIFA / EA FC "which team should I play with?" challenges.

## Stack

- **Vanilla JS + HTML Canvas** — single-page app, no UI framework
- **Vite** — build + dev server
- **MediaPipe Face Detection** (`@mediapipe/tasks-vision`) — multi-face bounding boxes
- **Google Fonts** — Bebas Neue (display), Inter (body), JetBrains Mono (labels)
- **Vercel** — hosting (auto-HTTPS for camera access)

## Quick start

```bash
npm install
npm run dev          # http://127.0.0.1:5173
```

The app requires camera access, which needs either `localhost` or HTTPS. For mobile testing on your LAN, use a tunnel like `ngrok http 5173` or deploy to Vercel.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Build icons (PNGs from SVGs) then run `vite build` |
| `npm run build:icons` | Generate PWA PNG icons from `public/icon.svg` via sharp |
| `npm run optimize:logos` | Compress `public/logos/` (converts large SVGs → PNG, palette-optimizes PNGs) |
| `npm test` | Run Vitest suite (`debug/verify.test.js`) |

## Project layout

```
data/teams.json         # 842 teams with id, name, country, leagueId, leagueName, logoPath
public/logos/           # Team crests (SVG + PNG, ~12 MB optimized)
public/icons/           # PWA icons (192/512 PNG, normal + maskable)
public/manifest.webmanifest
public/icon.svg         # PWA source icon (slot-shield motif)
src/
  main.js               # entry, render loop, spin orchestration
  camera.js             # getUserMedia setup
  faceDetection.js      # MediaPipe wrapper
  overlay.js            # Canvas drawing: video frame, carousel reel, result crest
  carousel.js           # Random team selection + easeOutQuint timing
  stateMachine.js       # loading → waiting → ready → spinning → result
  ui.js                 # DOM: chip bars, buttons, status strip, face badge
  style.css             # Stitch "EA FC Broadcast — Dark Pitch" design system
scripts/
  build-icons.js        # SVG → PNG for PWA icons (sharp)
  optimize-logos.js     # bulk logo optimization (sharp)
  fetch_logos.py        # (one-time) logo downloader
  fetch_teams.py        # (one-time) team metadata fetcher
  rebuild_teams.py      # (one-time) regenerate data/teams.json
debug/
  verify.test.js        # Vitest suite — verifies data outputs against teams_output.csv
  teams_output.csv      # Ground-truth source of truth (842 rows)
```

## State flow

```
loading  ──modelLoaded──▶  waiting  ──faceDetected──▶  ready
                          ▲                             │
                          └──────────faceLost───────────┘
                                                        │
                                                   spinTriggered
                                                        ▼
                          result  ◀─spinCompleted─  spinning
                            │                          ▲
                            └───spinAgainTriggered─────┘
```

Each state maps to a CSS class on `#app` (`.loading`, `.waiting`, `.ready`, `.spinning`, `.result`) so the UI transitions are declarative.

## Design system

The visual language is **EA FC Broadcast — Dark Pitch**, synthesized from Stitch mockups:

- **Palette**: pitch black `#05070a` → pitch green `#0a1f10` gradient base, neon `#c8ff00` accent, floodlight white `#f5f7ff`, signal red `#ff3b3b` (live indicator only)
- **Typography**: Bebas Neue (condensed display, always uppercase), Inter (body), JetBrains Mono (mono labels)
- **Motifs**: shield/crest frame, viewfinder L-brackets, progress rail, radial floodlight glow
- **Motion**: easeOutQuint reveals, 0.6 → 1.15 → 1.0 pop-in over 500 ms

## PWA / installability

- `manifest.webmanifest` with `display: standalone`, `orientation: portrait`, `theme_color: #05070a`
- SVG source icons + rasterized 192/512 PNGs (normal + maskable safe-zone-compliant)
- `apple-mobile-web-app-*` meta tags for iOS Safari Add-to-Home-Screen

After deploying to HTTPS, Chrome on Android will offer **"Add to Home Screen"** — launching full-screen with no browser chrome and a `#05070a` status bar.

## Testing

The `debug/verify.test.js` suite verifies 36 invariants against `debug/teams_output.csv` as the ground truth:

```bash
npm test
```

Covers: data integrity (842-way parity between CSV, JSON, and logo files), filter API correctness, carousel behavior, state machine transitions, empty-pool guards (regression for the REST OF WORLD + SPAIN stuck-spin bug), and build artifact validity.

## Deployment

```bash
# One-time
npm i -g vercel
vercel login

# From repo root
vercel          # preview deploy
vercel --prod   # production
```

Vercel auto-detects Vite, runs `npm run build` (which chains `build:icons && vite build`), and serves `/dist`. Camera access requires HTTPS — Vercel provides auto-TLS on `*.vercel.app`.

## Further reading

- `CONTEXT.md` — domain glossary (Filter, Player, Team, League, Spin, Screen state) and the architectural decisions behind platform, spin mechanics, face detection, and hosting choices.

## License

Private project. Team crests in `public/logos/` are © their respective clubs and used here under EA FC's licensed club artwork program.

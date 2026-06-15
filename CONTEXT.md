# Context

## Domain

An interactive AR filter that randomly assigns a football club to a person, primarily used for FIFA/EA FC challenges ("which team should I play with?").

## Glossary

- **Filter** — The web-based AR experience. Runs in a browser, uses the device camera, detects faces, and overlays football team visuals.
- **Player** — A person visible in the camera frame. The filter supports 1 or 2 players per session. Each player gets a team assigned independently.
- **Team** — A football club available in the current EA FC game (e.g., Real Madrid, PSG). The unit of random selection. The pool is bounded by EA FC licensing — if it's not in the game, it's not in the filter.
- **League** — A competition grouping of teams (e.g., Premier League, La Liga). Used as an optional filter to narrow the team pool before a spin.
- **Spin** — The act of randomly selecting a team for the user. Named after the "slot machine" metaphor common in these filters.
- **Screen state** — The filter progresses through: Loading → Waiting for faces (prompt: "Get in the frame!") → Ready (faces detected, spin button active) → Spinning (carousels running) → Result (logos + names above heads, "Spin Again" button appears). Tapping "Spin Again" immediately starts a new spin (Result → Spinning). If a face leaves the frame during Result, the logo stays at the last known face position.

## Decisions

- **Platform**: Web-based (browser). Not tied to any social media app. Accessible via URL.
- **Team pool**: All ~700+ clubs licensed in the current EA FC edition. The user can optionally narrow the pool to a specific league before spinning.
- **Spin trigger**: Tap a button overlaid on the camera feed. Face detection is used for overlay positioning across multiple faces, not for triggering.
- **Spin animation**: Two parallel slideshow frames — one above each detected face, flashing simultaneously. For 1 player, a single frame above their face. Each frame rapidly cycles through large (~100px) team crests one at a time inside a bordered display window, like a slot machine reel. Uses easeOutQuint timing over ~3.5 seconds — crests flash rapidly at start (~40ms each), gradually slowing to a stop. Team name fades in during the final slowdown. On landing, the winning crest scales up with a pop effect and the team name appears below.
- **Result screen**: After the carousel lands, the winning team logo and name remain visible above each player's head, anchored to their face position. No extra effects — the result stays on screen so players can screenshot or show friends.
- **Spin mechanics**: Both players share a single spin — one button tap, both results revealed simultaneously. Teams are sampled with replacement (both players can get the same team). Works for 1 or 2 players.
- **Team data source**: Primary source for logos is football-logos.cc (SVG/PNG, organized by league packs). Futbin as supplementary source for team metadata. Data is fetched once at build time and bundled as static assets — no runtime API dependency.
- **Face detection**: MediaPipe Face Detection (@mediapipe/tasks-vision). Provides bounding boxes for multiple faces, used to anchor team logos above each player's head.
- **Tech stack**: Vanilla JavaScript + HTML Canvas for rendering, bundled with Vite. No UI framework — the app is a single interactive screen with minimal UI controls.
- **Screenshot/recording**: None built in. Users capture the result manually via their device's screenshot feature.
- **Hosting**: Vercel. Free tier, auto-HTTPS (required for camera access), deployed from Git.
- **League selector UI**: Horizontal scrollable chip bar at the top of the screen. "All Teams" is the default first chip. Tapping a league chip filters the team pool instantly.
- **Device target**: Mobile-first (portrait, touch, front-facing camera). Desktop/laptop webcams supported via responsive layout but not optimized for.

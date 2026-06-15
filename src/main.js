import { startCamera } from './camera.js';
import { createFaceDetector } from './faceDetection.js';
import { createOverlay } from './overlay.js';
import { createUI } from './ui.js';
import { createTeamData } from './teamData.js';
import { createCarousel } from './carousel.js';
import { createStateMachine } from './stateMachine.js';
import teamsJson from '../data/teams.json';

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');

const narrowMq = window.matchMedia('(max-width: 380px)');
const statusStripEl = document.getElementById('statusStrip');
function applyNarrowPhase() {
  if (!statusStripEl) return;
  statusStripEl.classList.toggle('narrow-phase', narrowMq.matches);
}
applyNarrowPhase();
if (narrowMq.addEventListener) {
  narrowMq.addEventListener('change', applyNarrowPhase);
} else if (narrowMq.addListener) {
  narrowMq.addListener(applyNarrowPhase);
}

const teamData = createTeamData(teamsJson);
const sm = createStateMachine();

// Logo assets: a single sprite sheet + atlas index, plus a lazy-load map
// for fallback. Loaded asynchronously AFTER the face model resolves so
// sprite fetch doesn't compete with the WASM/model download for bandwidth.
const images = {
  sprite: null,
  atlas: new Map(),
  lazy: new Map(),
};

const overlay = createOverlay(canvas, images);

let detector = null;
let faces = [];
let lastFaces = [];
let activePool = teamData.getAll();
let carousels = [];
let resultTeams = [];
let resultStartTime = 0;
let spinStartTime = 0;
let spinDuration = 3500;
let consecutiveNoFaceFrames = 0;
const NO_FACE_DEBOUNCE = 15; // ~250ms at 60fps

sm.onTransition(({ to }) => {
  ui.setState(to);

  if (to === 'spinning') {
    spinStartTime = performance.now();
    startSpin();
  }
});

const ui = createUI(
  {
    leagueRow: document.getElementById('leagueRow'),
    countryRow: document.getElementById('countryRow'),
    leagueBar: document.getElementById('leagueBar'),
    spinBtn: document.getElementById('spinBtn'),
    spinAgainBtn: document.getElementById('spinAgainBtn'),
    prompt: document.getElementById('prompt'),
    loadingScreen: document.getElementById('loadingScreen'),
    faceBadge: document.getElementById('faceBadge'),
    faceBadgeText: document.getElementById('faceBadgeText'),
    statusStrip: document.getElementById('statusStrip'),
    viewfinderCorners: document.getElementById('viewfinderCorners'),
  },
  teamData,
  {
    onSpin: () => sm.dispatch('spinTriggered'),
    onSpinAgain: () => sm.dispatch('spinAgainTriggered'),
    onFilterChange: (leagueId, country) => {
      activePool = teamData.getFiltered(leagueId, country);
      ui.setPoolSize(activePool.length);
    },
  },
);

ui.setPoolSize(activePool.length);

function startSpin() {
  if (!activePool || activePool.length === 0) {
    console.warn('startSpin blocked: active pool is empty');
    return;
  }
  const carousel = createCarousel(activePool);
  carousels = [];
  resultTeams = [];

  const facesToUse = (faces.length > 0 ? faces : lastFaces).slice(0, 2);
  for (const face of facesToUse) {
    const spinResult = carousel.spin();

    const c = overlay.startCarousel(
      { team: spinResult.team, _cards: activePool, duration: spinResult.duration },
      face,
      video.videoWidth,
      video.videoHeight,
    );
    carousels.push(c);
    resultTeams.push(spinResult.team);
    spinDuration = spinResult.duration;
  }
}

function loop(timestamp) {
  if (!video.videoWidth) {
    requestAnimationFrame(loop);
    return;
  }

  overlay.drawVideoFrame(video, video.videoWidth, video.videoHeight);

  if (detector) {
    faces = detector.detect(video, timestamp);

    if (faces.length > 0) {
      lastFaces = faces;
      consecutiveNoFaceFrames = 0;
    } else {
      consecutiveNoFaceFrames++;
    }

    ui.setFaceCount(faces.length);

    if (sm.getState() === 'waiting' && faces.length > 0) {
      sm.dispatch('faceDetected');
    } else if (sm.getState() === 'ready' && consecutiveNoFaceFrames >= NO_FACE_DEBOUNCE) {
      consecutiveNoFaceFrames = 0;
      sm.dispatch('faceLost');
    }
  }

  if (sm.getState() === 'spinning') {
    const bannerProgress = Math.min((timestamp - spinStartTime) / spinDuration, 1);
    overlay.drawSpinBanner(bannerProgress);

    let allDone = true;
    for (let i = 0; i < carousels.length; i++) {
      const done = overlay.drawCarousel(carousels[i], timestamp);
      if (!done) allDone = false;
    }
    if (allDone && carousels.length > 0) {
      resultStartTime = timestamp;
      sm.dispatch('spinCompleted');
    }
  }

  if (sm.getState() === 'result') {
    const revealElapsed = timestamp - resultStartTime;
    const revealProgress = Math.min(revealElapsed / 500, 1);
    const facesToUse = (faces.length > 0 ? faces : lastFaces).slice(0, 2);

    for (let i = 0; i < resultTeams.length; i++) {
      const face = facesToUse[i];
      if (face) {
        overlay.drawResult(resultTeams[i], face, video.videoWidth, video.videoHeight, revealProgress);
      }
    }
  }

  requestAnimationFrame(loop);
}

// Load sprite sheet + atlas in the background. If either fails we fall
// back to lazy per-logo loads inside drawCrest — the app still works,
// just slower on first spin.
async function loadSpriteAssets() {
  try {
    const [sprite, atlasJson] = await Promise.all([
      new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = '/sprites/sheet.png';
      }),
      fetch('/sprites/atlas.json').then(r => r.json()),
    ]);
    images.sprite = sprite;
    images.atlas = new Map(Object.entries(atlasJson));
    console.log(`[perf] sprite loaded: ${images.atlas.size} cells`);
  } catch (err) {
    console.warn('[perf] sprite load failed, falling back to lazy per-logo loads:', err);
  }
}

function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.warn('SW registration failed:', err);
    });
  });
}

async function init() {
  try {
    const cam = await startCamera(video);
    detector = await createFaceDetector();
    sm.dispatch('modelLoaded');
    requestAnimationFrame(loop);

    // Non-blocking: kick off sprite + SW after the critical path resolves
    // so the user sees the camera UI as soon as possible.
    loadSpriteAssets();
    registerServiceWorker();
  } catch (err) {
    console.error('Init failed:', err);
    const safeMessage = String(err.message || 'Unknown error')
      .replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    document.getElementById('loadingScreen').innerHTML =
      `<div class="camera-error">
        <div class="loading-corners">
          <span class="corner tl"></span>
          <span class="corner tr"></span>
          <span class="corner bl"></span>
          <span class="corner br"></span>
        </div>
        <div class="camera-error-body">
          <div class="camera-error-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
              <line x1="1" y1="1" x2="23" y2="23"/>
            </svg>
          </div>
          <h1 class="camera-error-title">CAMERA ACCESS REQUIRED</h1>
          <div class="camera-error-divider"></div>
          <p class="camera-error-message">${safeMessage}</p>
          <p class="camera-error-hint">Allow camera permissions and reload the page</p>
        </div>
      </div>`;
  }
}

init();

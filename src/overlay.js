// Google Meet / Zoom style: the <video> element renders the camera with
// CSS object-fit: cover (the browser handles rotation, aspect ratio, and
// DPI correctly on every platform). This module provides a TRANSPARENT
// overlay canvas for UI elements (crests, shields, progress rings, banners)
// anchored to face positions that have been mapped through the same
// cover-viewport math the browser uses to display the video.

const CREST_SIZE = 130;
// HEAD_GAP positions the crest center above the top of the face bounding
// box. At ANDROID_SCALE = 2.0 the frame + team name span ~200 px below
// the crest center, so a 200 px gap places the team name roughly at the
// forehead level of the detected face rather than the chin / neck.
const HEAD_GAP = 200;
const TOTAL_FLASHES = 40;
// Carousel frame-to-crest ratio. Tightened from 1.4 so the card stays
// compact when ANDROID_SCALE is >1.5 — otherwise the 2× crest + 1.4×
// frame produced a card taller than the space above the face.
const CAROUSEL_FRAME_RATIO = 1.25;

const NEON = '#c8ff00';
const NEON_GLOW = 'rgba(200, 255, 0, 0.55)';
const NEON_SOFT = 'rgba(200, 255, 0, 0.22)';
const FLOOD = '#f5f7ff';
const PITCH_DARK = '#05070a';

const ABBR_COLORS = {
  rma: '#febe3c', bar: '#a50044', atm: '#cb3524',
  ars: '#ef0107', liv: '#c8102e', che: '#034694',
  mun: '#da291c', mci: '#6cabdd', tot: '#132257',
  bay: '#dc052d', bvb: '#fde100',
  psg: '#004170', olm: '#2faee0',
  juv: '#000000', int: '#0068a8', acm: '#fb090b', nap: '#12a0d7',
  ben: '#ff0000', por: '#003893',
  aja: '#d2122e',
};

function easeOutQuint(t) {
  return 1 - Math.pow(1 - t, 5);
}

function getAbbr(team) {
  const parts = team.logoPath.split('/');
  const file = parts[parts.length - 1];
  return file.replace(/\.(png|svg)$/, '').toUpperCase();
}

function getColor(team) {
  const abbr = getAbbr(team).toLowerCase();
  return ABBR_COLORS[abbr] || '#1a6b3a';
}

function shieldPath(ctx, cx, cy, size) {
  const w = size;
  const h = size * 1.18;
  const top = cy - h * 0.5;
  const bottom = cy + h * 0.5;
  const left = cx - w / 2;
  const right = cx + w / 2;
  const shoulderY = top + h * 0.38;
  ctx.beginPath();
  ctx.moveTo(cx, top);
  ctx.quadraticCurveTo(right, top, right, shoulderY);
  ctx.quadraticCurveTo(right, bottom - h * 0.18, cx, bottom);
  ctx.quadraticCurveTo(left, bottom - h * 0.18, left, shoulderY);
  ctx.quadraticCurveTo(left, top, cx, top);
  ctx.closePath();
}

function drawCrest(ctx, cx, cy, team, size, images) {
  const cell = images?.atlas?.get(team.logoPath);
  if (cell && images.sprite && images.sprite.complete && images.sprite.naturalWidth > 0) {
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.6)';
    ctx.shadowBlur = 16;
    ctx.shadowOffsetY = 4;
    ctx.drawImage(
      images.sprite,
      cell.x, cell.y, cell.w, cell.h,
      cx - size / 2, cy - size / 2, size, size,
    );
    ctx.restore();
    return;
  }

  if (images?.lazy) {
    let img = images.lazy.get(team.logoPath);
    if (!img) {
      img = new Image();
      img.src = team.logoPath;
      images.lazy.set(team.logoPath, img);
    }
    if (img.complete && img.naturalWidth > 0) {
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.6)';
      ctx.shadowBlur = 16;
      ctx.shadowOffsetY = 4;
      ctx.drawImage(img, cx - size / 2, cy - size / 2, size, size);
      ctx.restore();
      return;
    }
  }

  const color = getColor(team);
  const abbr = getAbbr(team);

  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.6)';
  ctx.shadowBlur = 16;
  ctx.shadowOffsetY = 4;

  shieldPath(ctx, cx, cy, size * 0.95);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = NEON;
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.shadowColor = 'transparent';
  ctx.fillStyle = FLOOD;
  ctx.font = `bold ${Math.round(size * 0.28)}px 'Bebas Neue', sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(abbr, cx, cy);

  ctx.restore();
}

// Compute the region of the video that CSS object-fit: cover makes
// visible on screen, in the video's intrinsic coordinate space.
// The browser does this internally; we mirror the math so face positions
// from MediaPipe map to the same screen pixels the user sees.
function computeCoverViewport(video) {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const sw = video.clientWidth;
  const sh = video.clientHeight;
  if (!vw || !vh || !sw || !sh) return null;
  const scale = Math.max(sw / vw, sh / vh);
  const visibleW = sw / scale;
  const visibleH = sh / scale;
  return {
    srcX: (vw - visibleW) / 2,
    srcY: (vh - visibleH) / 2,
    srcW: visibleW,
    srcH: visibleH,
    screenW: sw,
    screenH: sh,
  };
}

export function createOverlay(canvas, video, images, opts = {}) {
  const ctx = canvas.getContext('2d');

  // Android phones render the team card (crest + shield frame + name
  // text) noticeably smaller than iOS / desktop at the same CSS px, due
  // to Chrome-Android's compositor handling of device-pixel-ratio. A 2.0×
  // scale on Android brings visual parity without affecting other
  // platforms. The factor multiplies every card dimension below.
  const ANDROID_SCALE = opts.isAndroid ? 2.0 : 1.0;
  const BASE_CREST_SIZE = CREST_SIZE * ANDROID_SCALE;

  // "Real" landscape = touch device AND CSS viewport wider than tall.
  //
  // Touch detection has two redundant signals because real Android
  // Chrome + Vercel has been observed to return `false` from a cached
  // matchMedia('(hover: none) and (pointer: coarse)').matches while the
  // identical CSS @media query matches — the SPIN button rotates (CSS
  // trusts its own engine) but the banner stays horizontal (JS
  // disagrees). Live-query evaluation + UA-sniff fallback ensures
  // landscape mode fires whenever EITHER signal says "touch", which
  // matches the CSS's behavior.
  const touchMediaQuery = opts.touchMediaQuery;
  const uaSaysTouch = !!opts.uaSaysTouch;
  function isTouchNow() {
    try {
      if (touchMediaQuery && touchMediaQuery.matches) return true;
    } catch { /* matchMedia threw — fall through to UA */ }
    return uaSaysTouch;
  }
  function isRealLandscape() {
    if (!isTouchNow()) return false;
    const vw = video.clientWidth;
    const vh = video.clientHeight;
    return vw > 0 && vh > 0 && (vw / vh) > 1.05;
  }

  // Size the overlay canvas to match the video element 1:1. The canvas is
  // transparent — we only draw UI elements on it; the video is rendered by
  // the browser through the <video> element below us.
  function syncCanvasSize() {
    const w = Math.round(video.clientWidth * devicePixelRatio);
    const h = Math.round(video.clientHeight * devicePixelRatio);
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
  }

  // Clear the entire canvas at the start of every frame. Without this,
  // previous frames' pixels persist in the buffer, and semi-transparent
  // effects (the result-state burst gradient, shadow halos) accumulate
  // into visible concentric "tunnel" artifacts.
  function beginFrame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // Map a MediaPipe face bbox to canvas coordinates, accounting for the
  // cover crop and the CSS scaleX(-1) selfie mirror on the <video>.
  function getFaceAnchor(face) {
    const vp = computeCoverViewport(video);
    if (!vp) return null;
    const relX = (face.x + face.width / 2 - vp.srcX) / vp.srcW;
    const relY = (face.y - vp.srcY) / vp.srcH;
    // CSS scaleX(-1) on the video means screen-left shows video-right.
    // Mirror the face so the canvas UI aligns with the mirrored video.
    const cx = (1 - relX) * canvas.width;
    const topY = relY * canvas.height;
    return { cx, topY };
  }

  function startCarousel(teams, face) {
    const anchor = getFaceAnchor(face);
    if (!anchor) return null;
    const pool = teams._cards;
    const winTeam = teams.team;

    const sequence = [];
    for (let i = 0; i < TOTAL_FLASHES - 1; i++) {
      sequence.push(pool[Math.floor(Math.random() * pool.length)]);
    }
    sequence.push(winTeam);

    return {
      anchor,
      sequence,
      duration: teams.duration,
      startTime: null,
      team: winTeam,
    };
  }

  function drawCarousel(carousel, now) {
    if (!carousel.startTime) carousel.startTime = now;
    const elapsed = now - carousel.startTime;
    const t = Math.min(elapsed / carousel.duration, 1);

    const flashProgress = easeOutQuint(t);
    const flashIndex = Math.min(
      Math.floor(flashProgress * TOTAL_FLASHES),
      TOTAL_FLASHES - 1
    );

    const { cx, topY } = carousel.anchor;
    const isLandscape = isRealLandscape();
    // In landscape, dock the crest beside the face (to its right in
    // mirrored screen space) rather than above it, so it doesn't float
    // off the top of the shorter vertical axis.
    const crestSize = isLandscape ? BASE_CREST_SIZE * 0.85 : BASE_CREST_SIZE;
    const crestCy = isLandscape
      ? topY
      : topY - crestSize / 2 - HEAD_GAP;
    const crestCx = isLandscape
      ? cx + crestSize / 2 + HEAD_GAP
      : cx;
    const frameSize = crestSize * CAROUSEL_FRAME_RATIO;
    const ringRadius = frameSize * 0.62;

    ctx.save();
    ctx.fillStyle = 'rgba(5, 7, 10, 0.55)';
    ctx.beginPath();
    ctx.arc(crestCx, crestCy, ringRadius + 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(245, 247, 255, 0.1)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(crestCx, crestCy, ringRadius, -Math.PI / 2, Math.PI * 1.5);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = NEON;
    ctx.lineWidth = 4;
    ctx.shadowColor = NEON_GLOW;
    ctx.shadowBlur = 16;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.arc(crestCx, crestCy, ringRadius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * t);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.fillStyle = PITCH_DARK;
    ctx.strokeStyle = FLOOD;
    ctx.lineWidth = 3;
    ctx.shadowColor = NEON_GLOW;
    ctx.shadowBlur = 22;
    shieldPath(ctx, crestCx, crestCy, frameSize);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = NEON;
    ctx.lineWidth = 1.2;
    shieldPath(ctx, crestCx, crestCy, frameSize * 0.92);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = 0.85;
    shieldPath(ctx, crestCx, crestCy, frameSize * 0.88);
    ctx.clip();
    const curTeam = carousel.sequence[flashIndex];
    const streakLen = Math.max(0, 1 - t) * crestSize * 0.9;
    if (streakLen > 4) {
      const grad = ctx.createLinearGradient(crestCx, crestCy - crestSize / 2 - streakLen, crestCx, crestCy + crestSize / 2);
      grad.addColorStop(0, 'rgba(200, 255, 0, 0)');
      grad.addColorStop(1, 'rgba(200, 255, 0, 0.18)');
      ctx.fillStyle = grad;
      ctx.fillRect(crestCx - crestSize / 2, crestCy - crestSize / 2 - streakLen, crestSize, crestSize + streakLen);
    }
    drawCrest(ctx, crestCx, crestCy, curTeam, crestSize, images);
    ctx.restore();

    if (t > 0.72) {
      const alpha = Math.min((t - 0.72) / 0.28, 1);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = FLOOD;
      ctx.font = `bold ${Math.round(18 * ANDROID_SCALE)}px 'Bebas Neue', sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.shadowColor = 'rgba(0,0,0,0.9)';
      ctx.shadowBlur = 10;
      const nameY = isLandscape
        ? crestCy + frameSize * 0.52 + 8
        : crestCy + frameSize * 0.52 + 14;
      ctx.fillText(curTeam.name.toUpperCase(), crestCx, nameY);
      ctx.restore();
    }

    const ticks = 4;
    for (let i = 0; i < ticks; i++) {
      const a = -Math.PI / 2 + (i / ticks) * Math.PI * 2;
      const x1 = crestCx + Math.cos(a) * (ringRadius - 4);
      const y1 = crestCy + Math.sin(a) * (ringRadius - 4);
      const x2 = crestCx + Math.cos(a) * (ringRadius + 4);
      const y2 = crestCy + Math.sin(a) * (ringRadius + 4);
      ctx.save();
      ctx.strokeStyle = 'rgba(245, 247, 255, 0.45)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.restore();
    }

    return t >= 1;
  }

  function drawResult(team, face, revealProgress) {
    const anchor = getFaceAnchor(face);
    if (!anchor) return;
    const { cx, topY } = anchor;
    const p = Math.min(revealProgress, 1);
    const scale = p < 0.5
      ? 0.6 + (p / 0.5) * 0.55
      : 1.15 - (p - 0.5) / 0.5 * 0.15;
    const isLandscape = isRealLandscape();
    const baseSize = (isLandscape ? BASE_CREST_SIZE * 0.85 : BASE_CREST_SIZE) * scale;
    const crestCy = isLandscape
      ? topY
      : topY - baseSize / 2 - HEAD_GAP;
    const crestCx = isLandscape
      ? cx + baseSize / 2 + HEAD_GAP
      : cx;
    // Tightened from 1.55 to 1.3 so the result card fits above the face
    // even at ANDROID_SCALE = 2.0. The crest stays at the user-configured
    // scale; only the surrounding neon frame + typography offsets shrink.
    const frameSize = baseSize * 1.3;

    if (p > 0.05 && p < 0.85) {
      const burstAlpha = p < 0.4 ? (p / 0.4) : (0.85 - p) / 0.45;
      const burstRadius = frameSize * (0.7 + p * 0.6);
      ctx.save();
      ctx.globalAlpha = burstAlpha * 0.4;
      const burstGrad = ctx.createRadialGradient(crestCx, crestCy, frameSize * 0.3, crestCx, crestCy, burstRadius);
      burstGrad.addColorStop(0, NEON_SOFT);
      burstGrad.addColorStop(1, 'rgba(200, 255, 0, 0)');
      ctx.fillStyle = burstGrad;
      ctx.beginPath();
      ctx.arc(crestCx, crestCy, burstRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    ctx.save();
    ctx.globalAlpha = p;
    ctx.fillStyle = PITCH_DARK;
    ctx.strokeStyle = NEON;
    ctx.lineWidth = 3;
    ctx.shadowColor = NEON_GLOW;
    ctx.shadowBlur = 30;
    shieldPath(ctx, crestCx, crestCy, frameSize);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(245, 247, 255, 0.9)';
    ctx.lineWidth = 1.2;
    shieldPath(ctx, crestCx, crestCy, frameSize * 0.92);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = p;
    shieldPath(ctx, crestCx, crestCy, frameSize * 0.88);
    ctx.clip();
    drawCrest(ctx, crestCx, crestCy, team, baseSize, images);
    ctx.restore();

    if (p > 0.3) {
      const textAlpha = Math.min((p - 0.3) / 0.35, 1);
      ctx.save();
      ctx.globalAlpha = textAlpha;
      ctx.fillStyle = FLOOD;
      ctx.font = `bold ${Math.round((isLandscape ? 24 : 30) * ANDROID_SCALE)}px 'Bebas Neue', sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.shadowColor = 'rgba(0,0,0,0.95)';
      ctx.shadowBlur = 14;
      ctx.fillText(team.name.toUpperCase(), crestCx, crestCy + frameSize * 0.48 + (isLandscape ? 4 : 6));

      const leagueName = team.leagueName || '';
      const countryName = team.country ? team.country.toUpperCase().replace(/-/g, ' ') : '';
      const chipText = [leagueName, countryName].filter(Boolean).join(' · ');
      if (chipText) {
        // Gap scales with ANDROID_SCALE so breathing room stays proportional
        // to the team-name text height. At 1× (desktop) → 30/24 px gap,
        // same as before. At 2× (Android) → 60/48 px gap, which clears
        // the now-60 px-tall team-name text with ~10 px visual breathing
        // room on both platforms.
        const baseGap = isLandscape ? 24 : 30;
        const scaledGap = Math.round(baseGap * ANDROID_SCALE);
        const chipY = crestCy + frameSize * 0.48 + (isLandscape ? 4 : 6) + scaledGap;
        ctx.font = `500 ${Math.round(9 * ANDROID_SCALE)}px 'JetBrains Mono', monospace`;
        const chipW = ctx.measureText(chipText).width + 20;
        const chipH = Math.round(20 * ANDROID_SCALE);
        ctx.globalAlpha = textAlpha * 0.85;
        ctx.fillStyle = 'rgba(5, 7, 10, 0.72)';
        ctx.strokeStyle = 'rgba(245, 247, 255, 0.22)';
        ctx.lineWidth = 1;
        roundRect(ctx, crestCx - chipW / 2, chipY, chipW, chipH, 10);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = FLOOD;
        ctx.textBaseline = 'middle';
        ctx.fillText(chipText, crestCx, chipY + chipH / 2);
      }
      ctx.restore();
    }
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function drawSpinBanner(progress) {
    const w = canvas.width;
    const h = canvas.height;
    const isLandscape = isRealLandscape();

    if (isLandscape) {
      // In landscape the SPIN button docks to the right edge rotated 90°,
      // so we draw the banner along the LEFT edge rotated 90° to match.
      const bannerW = 40 * devicePixelRatio;
      ctx.save();
      ctx.fillStyle = 'rgba(5, 7, 10, 0.78)';
      ctx.fillRect(0, 0, bannerW, h);

      // Progress rail runs vertically down the banner's right edge.
      ctx.fillStyle = NEON;
      ctx.fillRect(bannerW - 2 * devicePixelRatio, 0, 2 * devicePixelRatio, h * progress);

      // Rotated text running top-to-bottom.
      ctx.translate(bannerW / 2, h / 2);
      ctx.rotate(Math.PI / 2);
      ctx.fillStyle = FLOOD;
      ctx.font = `bold ${22 * devicePixelRatio}px 'Bebas Neue', sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('PICKING YOUR CLUB…', 0, 0);
      ctx.restore();
      return;
    }

    // Portrait: horizontal banner across the top (original behavior).
    const bannerH = 46 * devicePixelRatio;
    ctx.save();
    ctx.fillStyle = 'rgba(5, 7, 10, 0.78)';
    ctx.fillRect(0, 0, w, bannerH);

    ctx.fillStyle = NEON;
    ctx.fillRect(0, bannerH - 2 * devicePixelRatio, w * progress, 2 * devicePixelRatio);

    ctx.fillStyle = 'rgba(200, 255, 0, 0.14)';
    const stripeW = 14 * devicePixelRatio;
    for (let x = -bannerH; x < w + bannerH; x += stripeW * 2) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + bannerH, bannerH);
      ctx.lineTo(x + bannerH + stripeW, bannerH);
      ctx.lineTo(x + stripeW, 0);
      ctx.closePath();
      ctx.fill();
    }

    ctx.fillStyle = FLOOD;
    ctx.font = `bold ${28 * devicePixelRatio}px 'Bebas Neue', sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('PICKING YOUR CLUB…', w / 2, bannerH / 2);
    ctx.restore();
  }

  return {
    syncCanvasSize,
    beginFrame,
    startCarousel,
    drawCarousel,
    drawResult,
    drawSpinBanner,
    getFaceAnchor,
  };
}

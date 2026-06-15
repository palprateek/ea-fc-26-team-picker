const CREST_SIZE = 130;
const HEAD_GAP = 20;
const TOTAL_FLASHES = 40;

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
  // 1) Sprite-sheet hit: the build script packed this logo into sheet.png.
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

  // 2) Lazy fallback: logo wasn't in the sprite (shouldn't happen in
  //    production), so attempt an on-demand load and paint a placeholder
  //    this frame. Subsequent frames will use the image once decoded.
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

  // 3) Generic fallback crest — colored shield with abbreviation text.
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

function mirrorX(canvasWidth, x) {
  return canvasWidth - x;
}

export function createOverlay(canvas, images) {
  const ctx = canvas.getContext('2d');

  function drawVideoFrame(video) {
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    const cw = canvas.clientWidth;
    const ch = canvas.clientHeight;
    if (!vw || !vh || !cw || !ch) return;

    // Android front cameras often report landscape dimensions even in
    // portrait orientation (e.g. 1280x720 when the phone is held tall).
    // Swap to match the visible portrait framing.
    const videoIsLandscape = vw > vh;
    const portraitW = videoIsLandscape ? vh : vw;
    const portraitH = videoIsLandscape ? vw : vh;

    // object-fit: cover math: scale the (portrait) video to fully cover
    // the viewport, then crop symmetrically. Sizing the canvas buffer to
    // the cropped region makes CSS object-fit: cover a 1:1 display, so
    // no second scaling distortion is applied.
    const scale = Math.max(cw / portraitW, ch / portraitH);
    const srcW = cw / scale;
    const srcH = ch / scale;
    const sx = (portraitW - srcW) / 2;
    const sy = (portraitH - srcH) / 2;

    canvas.width = Math.round(cw * devicePixelRatio);
    canvas.height = Math.round(ch * devicePixelRatio);

    ctx.save();
    // Mirror for selfie view + scale into the full canvas buffer.
    ctx.scale(-1, 1);
    if (videoIsLandscape) {
      // Video buffer is landscape but we want portrait framing: rotate 90°
      // then draw from the swapped source rect.
      ctx.translate(-canvas.width, 0);
      ctx.rotate(-Math.PI / 2);
      ctx.drawImage(
        video,
        sx, sy, srcW, srcH,
        0, 0, canvas.height, canvas.width,
      );
    } else {
      ctx.drawImage(
        video,
        sx, sy, srcW, srcH,
        -canvas.width, 0, canvas.width, canvas.height,
      );
    }
    ctx.restore();
  }

  function getFaceAnchor(face, videoWidth, videoHeight) {
    // MediaPipe reports face coordinates in the video buffer's native
    // coordinate space. For landscape-reported cameras, swap to portrait
    // before mapping to the canvas (which is sized to the cover-cropped
    // viewport).
    const vw = videoWidth;
    const vh = videoHeight;
    const videoIsLandscape = vw > vh;
    const portraitW = videoIsLandscape ? vh : vw;
    const portraitH = videoIsLandscape ? vw : vh;

    let fx, fy, fw, fh;
    if (videoIsLandscape) {
      fx = face.y;
      fy = vw - face.x - face.width;
      fw = face.height;
      fh = face.width;
    } else {
      fx = face.x;
      fy = face.y;
      fw = face.width;
      fh = face.height;
    }

    const cw = canvas.clientWidth;
    const ch = canvas.clientHeight;
    const scale = Math.max(cw / portraitW, ch / portraitH);
    const srcW = cw / scale;
    const srcH = ch / scale;
    const sx = (portraitW - srcW) / 2;
    const sy = (portraitH - srcH) / 2;

    const relX = (fx + fw / 2 - sx) / srcW;
    const relY = (fy - sy) / srcH;
    const cx = (1 - relX) * canvas.width; // mirror
    const topY = relY * canvas.height;
    return { cx, topY };
  }

  function startCarousel(teams, face, videoWidth, videoHeight) {
    const anchor = getFaceAnchor(face, videoWidth, videoHeight);
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
    const crestCy = topY - CREST_SIZE / 2 - HEAD_GAP;
    const frameSize = CREST_SIZE * 1.4;
    const ringRadius = frameSize * 0.62;

    ctx.save();
    ctx.fillStyle = 'rgba(5, 7, 10, 0.55)';
    ctx.beginPath();
    ctx.arc(cx, crestCy, ringRadius + 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(245, 247, 255, 0.1)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, crestCy, ringRadius, -Math.PI / 2, Math.PI * 1.5);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = NEON;
    ctx.lineWidth = 4;
    ctx.shadowColor = NEON_GLOW;
    ctx.shadowBlur = 16;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.arc(cx, crestCy, ringRadius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * t);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.fillStyle = PITCH_DARK;
    ctx.strokeStyle = FLOOD;
    ctx.lineWidth = 3;
    ctx.shadowColor = NEON_GLOW;
    ctx.shadowBlur = 22;
    shieldPath(ctx, cx, crestCy, frameSize);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = NEON;
    ctx.lineWidth = 1.2;
    shieldPath(ctx, cx, crestCy, frameSize * 0.92);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = 0.85;
    shieldPath(ctx, cx, crestCy, frameSize * 0.88);
    ctx.clip();
    const curTeam = carousel.sequence[flashIndex];
    const streakLen = Math.max(0, 1 - t) * CREST_SIZE * 0.9;
    if (streakLen > 4) {
      const grad = ctx.createLinearGradient(cx, crestCy - CREST_SIZE / 2 - streakLen, cx, crestCy + CREST_SIZE / 2);
      grad.addColorStop(0, 'rgba(200, 255, 0, 0)');
      grad.addColorStop(1, 'rgba(200, 255, 0, 0.18)');
      ctx.fillStyle = grad;
      ctx.fillRect(cx - CREST_SIZE / 2, crestCy - CREST_SIZE / 2 - streakLen, CREST_SIZE, CREST_SIZE + streakLen);
    }
    drawCrest(ctx, cx, crestCy, curTeam, CREST_SIZE, images);
    ctx.restore();

    if (t > 0.72) {
      const alpha = Math.min((t - 0.72) / 0.28, 1);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = FLOOD;
      ctx.font = "bold 20px 'Bebas Neue', sans-serif";
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.shadowColor = 'rgba(0,0,0,0.9)';
      ctx.shadowBlur = 10;
      ctx.fillText(curTeam.name.toUpperCase(), cx, crestCy + frameSize * 0.52 + 14);
      ctx.restore();
    }

    const ticks = 4;
    for (let i = 0; i < ticks; i++) {
      const a = -Math.PI / 2 + (i / ticks) * Math.PI * 2;
      const x1 = cx + Math.cos(a) * (ringRadius - 4);
      const y1 = crestCy + Math.sin(a) * (ringRadius - 4);
      const x2 = cx + Math.cos(a) * (ringRadius + 4);
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

  function drawResult(team, face, videoWidth, videoHeight, revealProgress) {
    const anchor = getFaceAnchor(face, videoWidth, videoHeight);
    const { cx, topY } = anchor;
    const p = Math.min(revealProgress, 1);
    const scale = p < 0.5
      ? 0.6 + (p / 0.5) * 0.55
      : 1.15 - (p - 0.5) / 0.5 * 0.15;
    const crestSize = CREST_SIZE * scale;
    const crestCy = topY - crestSize / 2 - HEAD_GAP;
    const frameSize = crestSize * 1.55;

    if (p > 0.05 && p < 0.85) {
      const burstAlpha = p < 0.4 ? (p / 0.4) : (0.85 - p) / 0.45;
      const burstRadius = frameSize * (0.7 + p * 0.6);
      ctx.save();
      ctx.globalAlpha = burstAlpha * 0.4;
      const burstGrad = ctx.createRadialGradient(cx, crestCy, frameSize * 0.3, cx, crestCy, burstRadius);
      burstGrad.addColorStop(0, NEON_SOFT);
      burstGrad.addColorStop(1, 'rgba(200, 255, 0, 0)');
      ctx.fillStyle = burstGrad;
      ctx.beginPath();
      ctx.arc(cx, crestCy, burstRadius, 0, Math.PI * 2);
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
    shieldPath(ctx, cx, crestCy, frameSize);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(245, 247, 255, 0.9)';
    ctx.lineWidth = 1.2;
    shieldPath(ctx, cx, crestCy, frameSize * 0.92);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = p;
    shieldPath(ctx, cx, crestCy, frameSize * 0.88);
    ctx.clip();
    drawCrest(ctx, cx, crestCy, team, crestSize, images);
    ctx.restore();

    if (p > 0.3) {
      const textAlpha = Math.min((p - 0.3) / 0.35, 1);
      ctx.save();
      ctx.globalAlpha = textAlpha;
      ctx.fillStyle = FLOOD;
      ctx.font = "bold 30px 'Bebas Neue', sans-serif";
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.shadowColor = 'rgba(0,0,0,0.95)';
      ctx.shadowBlur = 14;
      ctx.fillText(team.name.toUpperCase(), cx, crestCy + frameSize * 0.52 + 14);

      const leagueName = team.leagueName || '';
      const countryName = team.country ? team.country.toUpperCase().replace(/-/g, ' ') : '';
      const chipText = [leagueName, countryName].filter(Boolean).join(' · ');
      if (chipText) {
        const chipY = crestCy + frameSize * 0.52 + 50;
        ctx.font = "500 9px 'JetBrains Mono', monospace";
        const chipW = ctx.measureText(chipText).width + 20;
        const chipH = 20;
        ctx.globalAlpha = textAlpha * 0.85;
        ctx.fillStyle = 'rgba(5, 7, 10, 0.72)';
        ctx.strokeStyle = 'rgba(245, 247, 255, 0.22)';
        ctx.lineWidth = 1;
        roundRect(ctx, cx - chipW / 2, chipY, chipW, chipH, 10);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = FLOOD;
        ctx.textBaseline = 'middle';
        ctx.fillText(chipText, cx, chipY + chipH / 2);
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
    drawVideoFrame,
    startCarousel,
    drawCarousel,
    drawResult,
    drawSpinBanner,
    getFaceAnchor,
  };
}

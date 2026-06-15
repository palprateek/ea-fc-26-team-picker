// Optimize public/logos: convert large SVGs to small PNGs (they render at 130px
// anyway), and re-encode all PNGs through sharp's lossy palette optimizer.
// Run via: node scripts/optimize-logos.js

import sharp from 'sharp';
import { readdir, stat, rm, rename } from 'node:fs/promises';
import { resolve, dirname, extname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOGOS = resolve(__dirname, '..', 'public', 'logos');

const SVG_TO_PNG_THRESHOLD_KB = 80;   // convert SVGs larger than this
const PNG_RENDER_SIZE = 256;           // render SVGs at 256px (crisp at 2x DPR)

async function listFiles(ext) {
  const entries = await readdir(LOGOS);
  const out = [];
  for (const name of entries) {
    if (extname(name).toLowerCase() !== ext) continue;
    const full = resolve(LOGOS, name);
    const s = await stat(full);
    out.push({ name, full, size: s.size });
  }
  return out;
}

async function convertBigSvgs() {
  const svgs = await listFiles('.svg');
  let freed = 0;
  let converted = 0;
  for (const { name, full, size } of svgs) {
    if (size / 1024 < SVG_TO_PNG_THRESHOLD_KB) continue;
    const outName = `${basename(name, '.svg')}.png`;
    const outPath = resolve(LOGOS, outName);
    try {
      await sharp(full, { density: 300 })
        .resize(PNG_RENDER_SIZE, PNG_RENDER_SIZE, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .png({ palette: true, quality: 80, compressionLevel: 9 })
        .toFile(outPath);
      const newSize = (await stat(outPath)).size;
      freed += size - newSize;
      await rm(full);
      converted++;
      if (size > 200 * 1024) {
        console.log(`  ${name} (${(size/1024).toFixed(0)}K) → ${outName} (${(newSize/1024).toFixed(0)}K)`);
      }
    } catch (err) {
      console.warn(`  ! skipped ${name}: ${err.message}`);
    }
  }
  return { converted, freed };
}

async function optimizePngs() {
  const pngs = await listFiles('.png');
  let freed = 0;
  let optimized = 0;
  for (const { name, full, size } of pngs) {
    const tmp = `${full}.tmp`;
    try {
      await sharp(full)
        .resize(PNG_RENDER_SIZE, PNG_RENDER_SIZE, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .png({ palette: true, quality: 80, compressionLevel: 9 })
        .toFile(tmp);
      const newSize = (await stat(tmp)).size;
      if (newSize < size) {
        await rm(full);
        await rename(tmp, full);
        freed += size - newSize;
        optimized++;
      } else {
        await rm(tmp);
      }
    } catch (err) {
      console.warn(`  ! skipped ${name}: ${err.message}`);
      try { await rm(tmp); } catch {}
    }
  }
  return { optimized, freed };
}

async function totalSize() {
  const entries = await readdir(LOGOS);
  let s = 0;
  for (const name of entries) {
    const st = await stat(resolve(LOGOS, name));
    s += st.size;
  }
  return s;
}

async function main() {
  const before = await totalSize();
  console.log(`Before: ${(before/1024/1024).toFixed(2)} MB`);

  console.log('→ converting large SVGs to PNG...');
  const r1 = await convertBigSvgs();
  console.log(`  ${r1.converted} converted, freed ${(r1.freed/1024/1024).toFixed(2)} MB`);

  console.log('→ optimizing PNGs...');
  const r2 = await optimizePngs();
  console.log(`  ${r2.optimized} optimized, freed ${(r2.freed/1024/1024).toFixed(2)} MB`);

  const after = await totalSize();
  console.log(`\nAfter:  ${(after/1024/1024).toFixed(2)} MB`);
  console.log(`Saved:  ${((before-after)/1024/1024).toFixed(2)} MB (${((1 - after/before) * 100).toFixed(1)}%)`);
}

main().catch(err => { console.error(err); process.exit(1); });

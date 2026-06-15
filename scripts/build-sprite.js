// Build-time script: composite every team logo into a single PNG sprite sheet
// plus an atlas JSON describing cell positions. Dramatically reduces HTTP
// requests on cold start (842 → 2 files: sprite.png + atlas.json).
//
// Run via: npm run build:sprite

import sharp from 'sharp';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

const CELL = 128;            // cell size in pixels (high-DPI friendly)
const MAX_COLS = 32;         // cap width; grow vertically as needed
const OUT_DIR = resolve(ROOT, 'public', 'sprites');

async function main() {
  const teams = JSON.parse(await readFile(resolve(ROOT, 'data', 'teams.json'), 'utf8'));

  // Dedupe by logoPath — multiple teams often alias the same crest.
  const uniquePaths = [...new Map(teams.map(t => [t.logoPath, t])).values()]
    .map(t => t.logoPath);

  const cols = Math.min(uniquePaths.length, MAX_COLS);
  const rows = Math.ceil(uniquePaths.length / cols);
  const sheetW = cols * CELL;
  const sheetH = rows * CELL;

  const composites = [];
  const atlas = {};
  let failures = 0;

  for (let i = 0; i < uniquePaths.length; i++) {
    const logoPath = uniquePaths[i];
    const full = resolve(ROOT, 'public', logoPath.replace(/^\//, ''));
    const col = i % cols;
    const row = Math.floor(i / cols);
    const left = col * CELL;
    const top = row * CELL;

    try {
      const resized = await sharp(full, { density: 200 })
        .resize(CELL, CELL, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .toBuffer();
      composites.push({ input: resized, left, top });
      atlas[logoPath] = { col, row, x: left, y: top, w: CELL, h: CELL };
    } catch (err) {
      failures++;
      if (failures < 5) console.warn(`  ! skip ${logoPath}: ${err.message}`);
    }
  }

  await mkdir(OUT_DIR, { recursive: true });
  const spriteOut = resolve(OUT_DIR, 'sheet.png');
  await sharp({
    create: { width: sheetW, height: sheetH, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } },
  })
    .composite(composites)
    .png({ palette: true, compressionLevel: 9 })
    .toFile(spriteOut);

  const atlasOut = resolve(OUT_DIR, 'atlas.json');
  await writeFile(atlasOut, JSON.stringify(atlas));

  const { size } = await sharp(spriteOut).metadata().then(() =>
    readFile(spriteOut).then(b => ({ size: b.length }))
  );
  console.log(`  ✓ sprite sheet: ${uniquePaths.length - failures}/${uniquePaths.length} logos packed into ${cols}×${rows} grid`);
  console.log(`  ✓ sheet.png: ${(size/1024).toFixed(1)} KB  atlas.json: ${Object.keys(atlas).length} entries`);
}

main().catch(err => { console.error(err); process.exit(1); });

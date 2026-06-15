// Build-time script: rasterize icon.svg and icon-maskable.svg into the PNG
// sizes referenced by manifest.webmanifest. Run via `npm run build:icons`.
//
// Requires `sharp` as a devDependency. Output is committed to /public/icons
// so the build doesn't need sharp at runtime.

import sharp from 'sharp';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

const sources = [
  { name: 'icon', file: 'public/icon.svg' },
  { name: 'icon-maskable', file: 'public/icon-maskable.svg' },
];

const sizes = [192, 512];

async function main() {
  const outDir = resolve(ROOT, 'public', 'icons');
  await mkdir(outDir, { recursive: true });

  for (const { name, file } of sources) {
    const svg = await readFile(resolve(ROOT, file));
    for (const size of sizes) {
      const out = resolve(outDir, `${name}-${size}.png`);
      await sharp(svg, { density: 300 })
        .resize(size, size)
        .png()
        .toFile(out);
      console.log(`  ✓ ${name}-${size}.png`);
    }
  }
  console.log('PWA icons built to public/icons/');
}

main().catch(err => {
  console.error('build:icons failed:', err);
  process.exit(1);
});

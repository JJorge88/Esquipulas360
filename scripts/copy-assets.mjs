import { mkdir, copyFile, readdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const root = process.cwd();
const vendor = path.join(root, 'static/vendor');
await mkdir(path.join(vendor, 'fonts'), { recursive: true });
await mkdir(path.join(vendor, 'aframe'), { recursive: true });
const aframePath = path.join(vendor, 'aframe/aframe.min.js');
const aframe = JSON.parse(await readFile('content/vendor.json', 'utf8'));
let bundle;
try { bundle = await readFile(aframePath); } catch { /* Download only when absent. */ }
const digest = data => createHash('sha256').update(data).digest('hex');
if (!bundle || digest(bundle) !== aframe.sha256) {
  const response = await fetch(aframe.url, { signal: AbortSignal.timeout(45000) });
  if (!response.ok) throw new Error(`A-Frame: HTTP ${response.status}`);
  bundle = Buffer.from(await response.arrayBuffer());
  if (digest(bundle) !== aframe.sha256) throw new Error('La integridad de A-Frame no coincide.');
  await writeFile(aframePath, bundle);
}
for (const family of ['playfair-display', 'plus-jakarta-sans']) {
  const source = `node_modules/@fontsource-variable/${family}/files`;
  for (const file of await readdir(source)) {
    if (file.includes('-latin-') && file.endsWith('.woff2')) {
      await copyFile(path.join(source, file), path.join(vendor, 'fonts', file));
    }
  }
  await copyFile(`node_modules/@fontsource-variable/${family}/LICENSE`, path.join(vendor, 'fonts', `${family}-LICENSE`));
}
console.log('A-Frame y tipografías copiados a static/vendor.');

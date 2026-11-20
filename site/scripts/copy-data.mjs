// Copies the gated data files (../data/site) into static/data, where the site fetches them.
import { mkdirSync, copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../data/site');
const out = resolve(here, '../static/data');
mkdirSync(out, { recursive: true });
for (const f of ['films.json', 'numbers.json', 'layouts.json']) {
  if (!existsSync(resolve(src, f))) throw new Error(`missing ${f}: run the export scripts first`);
  copyFileSync(resolve(src, f), resolve(out, f));
}
// one file per layout (static/data/layouts/<name>.json): story pages fetch only the ones they draw
mkdirSync(resolve(out, 'layouts'), { recursive: true });
const all = JSON.parse(readFileSync(resolve(src, 'layouts.json'), 'utf8'));
for (const [name, lay] of Object.entries(all.layouts)) writeFileSync(resolve(out, 'layouts', `${name}.json`), JSON.stringify(lay));
console.log('data copied to static/data');

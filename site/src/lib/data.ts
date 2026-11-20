// Loads the three gated data files and resolves numbers by key. The page never types a data number.
import { base } from '$app/paths';

export type Group = 'imdb' | 'both' | 'lb' | 'lb500';
export interface Film {
  id: string; t: string; aka?: string[]; y: number; rt?: number; d: string[]; g: string[]; c: string; cs: string[];
  l: string; s: number; ir?: number; lr?: number; iR?: number; iv?: number; lR: number; lv?: number; grp: Group;
  wd?: number; wdn?: string[]; lw?: number; t3w?: number; t3n?: number;
}
export interface Deco {
  labels?: { t: string; x: number; y: number; a: 'start' | 'middle' | 'end'; c: string }[];
  lines?: { x1: number; y1: number; x2: number; y2: number; c: string }[];
  rects?: { x: number; y: number; w: number; h: number; c: string }[];
  xticks?: { v: string; x: number; y: number }[];
  yticks?: { v: string; y: number; x: number }[];
}
export interface Variant { w: number; h: number; r: number; xy: number[]; deco: Deco; radii?: number[] }
export interface Layout { keys: string[]; shape: 'circle' | 'square'; wide: Variant; narrow: Variant; rows?: string[]; [k: string]: unknown }
export interface Numbers { meta: Record<string, unknown>; n: Record<string, number>; series: Record<string, any> }

const cache = new Map<string, Promise<any>>();
function get<T>(file: string): Promise<T> {
  if (!cache.has(file)) {
    cache.set(file, fetch(`${base}/data/${file}`).then((r) => {
      if (!r.ok) throw new Error(`could not load ${file} (${r.status})`);
      return r.json();
    }));
  }
  return cache.get(file)!;
}

// Display only (the data and its checks are untouched): proper spellings for names the source stores without
// diacritics, and typographic apostrophes in titles, to match the rest of the copy.
const DISPLAY_NAMES: Record<string, string> = { 'Jasmila Zbanic': 'Jasmila Žbanić' };
const display = (f: Film): Film => ({
  ...f,
  t: f.t.replace(/'/g, '’'),
  d: f.d.map((n) => DISPLAY_NAMES[n] ?? n),
  wdn: f.wdn?.map((n) => DISPLAY_NAMES[n] ?? n)
});
let displayed: Promise<Film[]> | null = null;
export const loadFilms = () => (displayed ??= get<{ films: Film[] }>('films.json').then((d) => d.films.map(display)));
export const loadNumbers = () => get<Numbers>('numbers.json');
export const loadLayouts = () => get<{ layouts: Record<string, Layout> }>('layouts.json').then((d) => d.layouts);
/** One layout on its own (a few KB to ~100 KB), for pages that draw only that arrangement. */
export const loadLayout = (name: string) => get<Layout>(`layouts/${name}.json`);

/** A number from numbers.json, formatted for reading. Missing keys are shown loudly, never guessed. */
export function num(N: Numbers, key: string): string {
  const v = N.n[key];
  if (v === undefined) {
    console.error(`numbers.json has no key "${key}"`);
    return `⟨${key}?⟩`;
  }
  // thousands separators only for big counts, so years read as 1997, not 1,997
  return Number.isInteger(v) && Math.abs(v) >= 10000 ? v.toLocaleString('en-GB') : String(v);
}

/** Replace {key} placeholders in a label with numbers from numbers.json. */
export const fill = (N: Numbers | null, text: string) =>
  N ? text.replace(/\{([^}]+)\}/g, (_, k) => num(N, k)) : text.replace(/\{([^}]+)\}/g, '');

/** What a dot key refers to: a film entry on a list, a film, a director, or a film on a director's strip. */
export function parseKey(key: string): { id?: string; list?: 'i' | 'l'; director?: string } {
  if (key.startsWith('d:')) return { director: key.slice(2) };
  if (key.startsWith('s:')) {
    // s:Director|tt0000000 (a film on a director's strip) or s:Director|tt0000000:i (that film as an IMDb entry)
    const [d, rest] = key.slice(2).split('|');
    const [id, list] = rest.split(':');
    return { director: d, id, list: list as 'i' | 'l' | undefined };
  }
  const [id, list] = key.split(':');
  return { id, list: list as 'i' | 'l' | undefined };
}

export const groupLabel: Record<Group, string> = {
  imdb: 'Only on IMDb’s list',
  both: 'On both lists',
  lb: 'Only on Letterboxd’s list',
  lb500: 'Letterboxd 251 to 500 only'
};

/** Reads a CSS custom property so canvas drawing uses the same tokens as the page. */
export function token(name: string): string {
  if (typeof document === 'undefined') return '#888';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export const prefersReducedMotion = () =>
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

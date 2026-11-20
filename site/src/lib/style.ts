// Colour rules shared by every chart: IMDb yellow, Letterboxd blue-purple, grey for films on both lists.
import { parseKey, token, type Film } from './data';
import type { DotStyle } from './engine/DotChart.svelte';

export interface Palette { imdb: string; imdbEdge: string; lb: string; lbEdge: string; both: string; faint: string; ink: string; muted: string; bg: string }
let cached: Palette | null = null;
/** Forget the cached colours, after a page switches theme (the dark finale). */
export const resetPalette = () => { cached = null; };
export function palette(): Palette {
  if (!cached && typeof document !== 'undefined') {
    cached = { imdb: token('--imdb'), imdbEdge: token('--imdb-edge'), lb: token('--lb'), lbEdge: token('--lb-edge'), both: token('--both'),
      faint: token('--faint'), ink: token('--ink'), muted: token('--muted'), bg: token('--bg') };
  }
  return cached ?? { imdb: '#f5c518', imdbEdge: '#9c7a00', lb: '#6b6bf0', lbEdge: '#4f4fd6', both: '#8e8c85', faint: '#dad7cf', ink: '#1f1e1b', muted: '#6b6962', bg: '#f6f5f1' };
}

export const imdbDot = (p: Palette): DotStyle => ({ fill: p.imdb, stroke: p.imdbEdge });
export const lbDot = (p: Palette): DotStyle => ({ fill: p.lb });
export const bothDot = (p: Palette): DotStyle => ({ fill: p.both });

/** Default colouring: shared films grey, otherwise the colour of the list the dot stands for. */
export function byGroup(byId: Map<string, Film>) {
  return (key: string): DotStyle => {
    const p = palette();
    const { id, list } = parseKey(key);
    const f = id ? byId.get(id) : undefined;
    if (!f) return { fill: p.faint };
    if (f.grp === 'both') return bothDot(p);
    if (list === 'i' || (!list && f.grp === 'imdb')) return imdbDot(p);
    return lbDot(p);
  };
}

/** Colour by which list a dot stands for, ignoring overlap (used where both lists are shown side by side). */
export function byList(key: string): DotStyle {
  const p = palette();
  return parseKey(key).list === 'i' ? imdbDot(p) : lbDot(p);
}

export const dimmed = (d: DotStyle, on: boolean): DotStyle => (on ? d : { fill: palette().faint, alpha: 0.9 });

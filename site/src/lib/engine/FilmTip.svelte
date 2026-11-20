<!-- The hover / tap card for one film: title, who made it, each list's rank (with a small track showing where
     on the list it sits) and rating, and one plain sentence comparing the two ranks. All values come from films.json. -->
<script lang="ts">
  import type { Film } from '$lib/data';
  /** lbScope 250: the story's Top 250 vs Top 250 pages. Letterboxd ranks past 250 aren't shown (the film counts as not on
      Letterboxd's list there), and its track runs 1 to 250 like IMDb's. 500: Letterboxd's whole Top 500 is in play. */
  let { film, note = '', compareLine = true, lbScope = 500 }: { film: Film; note?: string; compareLine?: boolean; lbScope?: 250 | 500 } = $props();

  const lbIn250 = $derived(film.lr !== undefined && film.lr <= 250);
  // in the Top 250 view a Letterboxd rank past 250 is treated as "not on the list"
  const lr = $derived(lbScope === 250 && !lbIn250 ? undefined : film.lr);
  const compare = $derived.by(() => {
    if (lbScope === 250) {
      if (film.ir === undefined) return 'Not in IMDb’s Top 250';
      if (lr === undefined) return 'Not in Letterboxd’s Top 250';
    }
    if (film.ir === undefined) return film.lr !== undefined && film.lr > 250 ? 'Not in IMDb’s top 250; just outside Letterboxd’s' : 'Not in IMDb’s top 250';
    if (film.lr === undefined) return 'Not in Letterboxd’s top 500';
    const d = film.lr - film.ir;
    if (d === 0) return 'Ranked the same on both lists';
    return `Letterboxd ranks it ${Math.abs(d)} ${Math.abs(d) === 1 ? 'place' : 'places'} ${d > 0 ? 'lower' : 'higher'}`;
  });
  // marker position on a track: IMDb's runs 1 to 250, Letterboxd's 1 to 500 with its top 250 shaded
  const pos = (rank: number | undefined, of: number) => (rank === undefined ? null : ((rank - 1) / (of - 1)) * 100);
</script>

<div class="title">{film.t} <span class="year">{film.y}</span></div>
<div class="meta">{film.d.join(', ')} · {film.c}{film.rt ? ` · ${film.rt} min` : ''}</div>

<div class="rows">
  <div class="row">
    <span class="name imdb">IMDb</span>
    <span class="rank">{film.ir ? `#${film.ir}` : '—'}</span>
    <span class="track"><span class="fill imdb" style:width="100%"></span>
      {#if pos(film.ir, 250) !== null}<span class="mark imdb" style:left="{pos(film.ir, 250)}%"></span>{/if}</span>
    <span class="rating">{lbScope === 250 && !film.ir ? '–' : film.iR?.toFixed(1) ?? '–'}</span>
  </div>
  <div class="row">
    <span class="name lb">Letterboxd</span>
    <span class="rank">{lr ? `#${lr}` : '—'}</span>
    <span class="track"><span class="fill lb" style:width={lbScope === 250 ? '100%' : '50%'}></span>
      {#if pos(lr, lbScope) !== null}<span class="mark lb" class:out={!lbIn250} style:left="{pos(lr, lbScope)}%"></span>{/if}</span>
    <span class="rating">{lr ? film.lR.toFixed(1) : '–'}</span>
  </div>
</div>
{#if compareLine}<div class="compare">{compare}</div>{/if}
{#if note}<div class="note">{note}</div>{/if}

<style>
  .title { font: 560 16px/1.2 var(--display); letter-spacing: -0.01em; color: var(--ink); }
  .year { font: 500 14px var(--sans); color: var(--muted); margin-left: 2px; }
  .meta { color: var(--muted); font-size: 12px; margin: 3px 0 10px; }
  .rows { display: grid; gap: 6px; }
  .row { display: grid; grid-template-columns: 84px 44px minmax(60px, 1fr) 28px; align-items: center; gap: 8px; }
  .name { font-size: 12px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; }
  .name.imdb { color: var(--imdb-ink); }
  .name.lb { color: var(--lb-ink); }
  .rank { font: 600 16px var(--sans); font-variant-numeric: tabular-nums; }
  .rating { font-size: 12px; color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
  .track { position: relative; height: 6px; background: var(--grid); border-radius: 99px; }
  .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 99px; opacity: 0.22; }
  .fill.imdb { background: var(--imdb); }
  .fill.lb { background: var(--lb); }
  .mark { position: absolute; top: 50%; width: 10px; height: 10px; border-radius: 50%; transform: translate(-50%, -50%); box-shadow: 0 0 0 2px var(--surface); }
  .mark.imdb { background: var(--imdb); outline: 1px solid var(--imdb-edge); outline-offset: -1px; }
  .mark.lb { background: var(--lb); }
  .mark.lb.out { background: var(--surface); outline: 1.5px solid var(--lb); outline-offset: -1.5px; }
  .compare { margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--grid); font-size: 12px; color: var(--ink); }
  .note { font-size: 12px; color: var(--muted); margin-top: 4px; }
</style>

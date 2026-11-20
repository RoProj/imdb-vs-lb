<!--
  Beat 5 of the guided story: "Where they disagree most".
  Chart: IMDb's ranks 1-250 in a column left of the centre line, Letterboxd's 1-500 to the right (251-500 shaded:
  outside its Top 250, known only for IMDb's films). A line joins each film's two ranks; a flat line means agreement.
  Every film named here is picked by a rule from the ranks in films.json (which the gate checks), not by hand.
-->
<script lang="ts">
  import { base } from '$app/paths';
  import { onMount } from 'svelte';
  import Beat from '$lib/story/Beat.svelte';
  import type { StageStep } from '$lib/story/StoryStage.svelte';
  import { loadFilms, loadLayout, loadNumbers, num, parseKey, type Film, type Layout, type Numbers } from '$lib/data';
  import { byGroup, palette } from '$lib/style';
  import type { DotStyle } from '$lib/engine/DotChart.svelte';
  import BeatOpener from '$lib/story/BeatOpener.svelte';
  import NextLink from '$lib/story/NextLink.svelte';
  import '$lib/story/story.css';

  let films = $state<Film[]>([]);
  let N = $state<Numbers | null>(null);
  let lay = $state<Layout | null>(null);
  let error = $state('');
  const byId = $derived(new Map(films.map((f) => [f.id, f])));
  const n = (key: string) => (N ? num(N, key) : '');
  const listSize = $derived(N?.n['lists.size'] ?? 0);

  const INCEPTION = 'tt1375666', SHAWSHANK = 'tt0111161', HARAKIRI = 'tt0056058';
  const inception = $derived(byId.get(INCEPTION));
  const shawshank = $derived(byId.get(SHAWSHANK));
  const harakiri = $derived(byId.get(HARAKIRI));
  const chart = $derived(films.filter((f) => f.grp !== 'lb500'));
  // IMDb's highest-ranked films that aren't in Letterboxd's Top 250
  const imdbFavs = $derived(chart.filter((f) => f.ir !== undefined && !(f.lr !== undefined && f.lr <= 250)).sort((a, b) => a.ir! - b.ir!).slice(0, 4));
  // Letterboxd's highest-ranked films that aren't on IMDb's list at all
  const lbFavs = $derived(chart.filter((f) => f.ir === undefined && f.lr !== undefined && f.lr <= 250).sort((a, b) => a.lr! - b.lr!).slice(0, 4));
  // films on both lists, furthest apart in each direction
  const shared = $derived(chart.filter((f) => f.grp === 'both'));
  const imdbHigher = $derived(shared.slice().sort((a, b) => (b.lr! - b.ir!) - (a.lr! - a.ir!)).slice(0, 3));
  const lbHigher = $derived(shared.slice().sort((a, b) => (b.ir! - b.lr!) - (a.ir! - a.lr!)).slice(0, 3));
  // long titles lose their subtitle first ("The Human Condition III: A Soldier's Prayer" -> "The Human Condition III")
  const short = (t: string) => { const main = t.length > 24 ? t.split(':')[0] : t; return main.length > 26 ? `${main.slice(0, 24).trimEnd()}…` : main; };
  const rk = (f: Film, side: 'i' | 'l') => (side === 'i' ? (f.ir ? `#${f.ir}` : 'not on its list') : f.lr ? `#${f.lr}` : 'not in its top 500');

  const IDS = ['inception', 'all', 'the-top', 'imdb-favourites', 'letterboxd-favourites', 'far-apart', 'one-list', 'end'];
  const steps = $derived.by((): StageStep[] => {
    const base = byGroup(byId), p = palette();
    const film = (k: string) => byId.get(parseKey(k).id ?? '');
    // Letterboxd ranks 251-500 are outside its Top 250: drawn lighter
    const dot = (k: string): DotStyle => { const f = film(k); return k.endsWith(':l') && (f?.lr ?? 0) > 250 ? { ...base(k), alpha: 0.45 } : base(k); };
    const dim: DotStyle = { fill: p.faint, alpha: 0.6 };
    const only = (ids: string[]) => (k: string) => (ids.includes(parseKey(k).id ?? '') ? dot(k) : dim);
    const agree = (id: string) => {
      // colour: which list ranks the film higher; strength: how far apart the two ranks are
      const f = byId.get(id);
      if (!f?.ir || !f.lr) return null;
      const d = f.lr - f.ir;
      return { color: d > 0 ? p.imdbEdge : p.lbEdge, alpha: 0.12 + 0.45 * Math.min(1, Math.abs(d) / 150), width: 1 };
    };
    const lines = (ids: string[]) => (id: string) => (ids.includes(id) ? { color: p.ink, alpha: 0.85, width: 2 } : agree(id) && { color: p.faint, alpha: 0.35, width: 1 });
    const keysOf = (ids: string[]) => (lay?.keys ?? []).filter((k) => ids.includes(parseKey(k).id ?? ''));
    const top = [SHAWSHANK, HARAKIRI];
    const imdbIds = imdbFavs.map((f) => f.id), lbIds = lbFavs.map((f) => f.id);
    const apart = [...imdbHigher, ...lbHigher].map((f) => f.id);
    return [
      { view: { keys: keysOf([INCEPTION]), pad: 40 }, style: only([INCEPTION]), link: lines([INCEPTION]),
        stat: inception ? [`#${inception.ir}`, `#${inception.lr}`] : undefined,
        notes: inception ? [
          { key: `${INCEPTION}:i`, title: 'Inception', text: `IMDb #${inception.ir}`, dx: -30, dy: 34 },
          { key: `${INCEPTION}:l`, title: 'Inception', text: `Letterboxd #${inception.lr}`, dx: 30, dy: -30 }
        ] : [] },
      { view: {}, style: dot, link: agree },
      { view: { keys: keysOf(top), pad: 30, alignTop: true, maxK: 3 }, style: only(top), link: lines(top),
        notes: shawshank && harakiri ? [
          { key: `${SHAWSHANK}:i`, title: shawshank.t, text: `IMDb #${shawshank.ir} · Letterboxd #${shawshank.lr}`, dx: -20, dy: 92 },
          { key: `${HARAKIRI}:l`, title: harakiri.t, text: `Letterboxd #${harakiri.lr} · IMDb #${harakiri.ir}`, dx: 20, dy: 30 }
        ] : [] },
      { view: { keys: keysOf(imdbIds), pad: 30 }, style: only(imdbIds), link: lines(imdbIds) },
      // zoom in on Letterboxd's column alone: these films have no IMDb rank to show
      { view: { keys: keysOf(lbIds), pad: 22, alignTop: true, maxK: 5 }, style: only(lbIds), link: lines([]),
        notes: lbFavs.map((f) => ({ key: `${f.id}:l`, title: `${short(f.t)} · #${f.lr}`, dx: -28, dy: 5 })) },
      { view: { keys: keysOf(apart), pad: 30 }, style: only(apart), link: lines(apart) },
      { view: {}, style: (k) => (film(k)?.grp === 'both' ? dim : dot(k)), link: () => null, stat: [n('overlap.imdb_only'), n('overlap.lb_only')] },
      { view: {}, style: dot, link: agree }
    ];
  });

  onMount(async () => {
    try {
      const [f, nn, L1] = await Promise.all([loadFilms(), loadNumbers(), loadLayout('ranks.ladder')]);
      films = f; N = nn; lay = L1;
    } catch (e) { error = String(e); }
  });
</script>

<svelte:head><title>Where they disagree most · Quantifying Taste</title><meta name="description" content="The films IMDb’s and Letterboxd’s crowds disagree about most." /><meta property="og:title" content="Where they disagree most · Quantifying Taste" /><meta property="og:description" content="The films IMDb’s and Letterboxd’s crowds disagree about most." /><meta property="og:type" content="article" /><link rel="preload" href="{base}/data/layouts/ranks.ladder.json" as="fetch" crossorigin="anonymous" /></svelte:head>

<header class="story-top">
  <a href="../">Quantifying Taste</a>
</header>

<BeatOpener beat={5} label="Where they disagree most" title="One crowd’s classic is the other’s also-ran" dek="Even the films both lists include can sit hundreds of places apart." />

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if N && lay && inception && shawshank && harakiri}
  <Beat lbTop500
    beat={5}
    layout={lay}
    {steps}
    ids={IDS}
    numbers={N}
    films={byId}
    summary="Chart: two columns of ranks, IMDb’s 1 to 250 on the left of a centre line and Letterboxd’s 1 to 500 on the right. A line joins each film’s two ranks; a flat line means the two lists agree, a steep one that they disagree. The cards name the films each step highlights."
  >
    {#snippet keyNote()}
      Each dot is a film’s rank on one list, number 1 at the top. A line joins a film’s two ranks; its colour shows which
      list ranks it higher. Letterboxd’s ranks 251 to 500 are shaded: outside its Top 250, shown only to place IMDb’s films.
    {/snippet}
    {#snippet card(i)}
      {#if i === 0}
        <h2 class="lead">Remember <em>Inception</em>?</h2>
        <p>#{inception.ir} on IMDb’s list, <strong>#{inception.lr}</strong> on Letterboxd’s: {listSize - (inception.lr ?? 0)} places from falling off. It isn’t the only film the two crowds see so differently.</p>
      {:else if i === 1}
        <p>Here are both lists as two columns of ranks, number 1 at the top. A line joins each film’s two ranks: the {n('overlap.both')} films on both lists, and {n('overlap.imdb_only.lb251_500')} of IMDb’s films that Letterboxd ranks between 251 and 500, shaded.</p>
        <p>Flat lines mean the crowds agree. Yellow lines slope down toward Letterboxd: IMDb ranks the film higher. Purple ones slope the other way.</p>
      {:else if i === 2}
        <h2 class="lead">At the very top, each crowd has its own number one</h2>
        <p><em>{shawshank.t}</em> is IMDb’s #{shawshank.ir} and Letterboxd’s #{shawshank.lr}. <em>{harakiri.t}</em> is Letterboxd’s #{harakiri.lr} and IMDb’s #{harakiri.ir}.</p>
      {:else if i === 3}
        <h2 class="lead"><span class="sw imdb" aria-hidden="true"></span>IMDb’s favourites that miss Letterboxd’s Top 250</h2>
        <ul class="entries">
          {#each imdbFavs as f}
            <li>
              <span class="rank">#{f.ir}</span>
              <span class="film"><span class="t">{f.t}</span> <span class="y">{f.y}</span></span>
              <span class="who">{f.lr ? `Letterboxd #${f.lr}` : 'Not in Letterboxd’s Top 500'}</span>
            </li>
          {/each}
        </ul>
      {:else if i === 4}
        <h2 class="lead"><span class="sw lb" aria-hidden="true"></span>Letterboxd’s favourites that miss IMDb’s Top 250</h2>
        <ul class="entries">
          {#each lbFavs as f}
            <li>
              <span class="rank">#{f.lr}</span>
              <span class="film"><span class="t">{f.t}</span> <span class="y">{f.y}</span></span>
              <span class="who">{f.d.join(' and ')}</span>
            </li>
          {/each}
        </ul>
      {:else if i === 5}
        <h2 class="lead">On both lists, but far apart</h2>
        <ul class="films">
          {#each imdbHigher as f}<li class="imdb"><em>{f.t}</em> · IMDb #{f.ir}, Letterboxd #{f.lr}</li>{/each}
          {#each lbHigher as f}<li class="lb"><em>{f.t}</em> · Letterboxd #{f.lr}, IMDb #{f.ir}</li>{/each}
        </ul>
      {:else if i === 6}
        <h2 class="lead">And most films are on only one list</h2>
        <p><strong>{n('overlap.imdb_only')}</strong> of IMDb’s 250 aren’t in Letterboxd’s Top 250, and <strong>{n('overlap.lb_only')}</strong> of Letterboxd’s aren’t on IMDb’s. Only <strong>{n('overlap.both')}</strong> are on both.</p>
      {:else}
        <h2 class="lead">Two Top 250s. Only {n('overlap.both')} films in common.</h2>
        <p>One crowd’s list is more American, more English-language and built around Hollywood’s best-known directors. The other reaches further abroad, to Japan and Europe and to international art cinema.</p>
        <p class="aside">The lists can’t tell us who their voters are. They do suggest two crowds with different tastes.</p>
      {/if}
    {/snippet}
    {#snippet next()}
      <NextLink href="../your-turn/" small="Next · 6 of 6" q="Where does your favourite film land?" arrow="→" />
    {/snippet}
  </Beat>

{:else}
  <p class="col muted">Loading…</p>
{/if}


<style>
  /* a dot in the list's colour before the heading, like the Key's swatches (same as the women directors page) */
  .sw { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 8px; vertical-align: 0.06em; }
  .sw.imdb { background: var(--imdb); box-shadow: inset 0 0 0 1px var(--imdb-edge); }
  .sw.lb { background: var(--lb); }
  /* one entry per film, as on the women directors page: its rank on that list in a narrow column, then title and
     year, one grey detail line underneath; thin rules between entries */
  .entries { list-style: none; margin: 4px 0 0; padding: 0; }
  .entries li {
    display: grid; grid-template-columns: 3.2em 1fr; column-gap: 8px; row-gap: 2px; align-items: baseline;
    padding: 10px 0; border-top: 1px solid var(--grid);
  }
  .entries li:first-child { border-top: 0; padding-top: 2px; }
  .entries li:last-child { padding-bottom: 0; }
  .rank { grid-row: 1 / span 2; font: 600 14px var(--sans); color: var(--muted); font-variant-numeric: tabular-nums; }
  .film { grid-column: 2; line-height: 1.3; }
  .t { font-weight: 600; }
  .y { color: var(--muted); font-size: 14px; font-variant-numeric: tabular-nums; }
  .who { grid-column: 2; color: var(--muted); font-size: 14px; line-height: 1.35; }
  .films { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; font-size: 16px; line-height: 1.4; }
  .films li.imdb { border-left: 3px solid var(--imdb); padding-left: 8px; }
  .films li.lb { border-left: 3px solid var(--lb); padding-left: 8px; }
</style>

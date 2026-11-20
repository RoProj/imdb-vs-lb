<!--
  Beat 4 of the guided story: "Who's behind the camera": films directed by women.
  Sober tone: counts beside every percentage, the uncertainty stated, the method stated (director gender from Wikidata).
  Layout: each list is a block of 250 dots either side of the centre line, filled from the top, films a woman directed
  or co-directed coming first, so they sit together in the top row.
  Every number and name comes from numbers.json or films.json; "could be chance" is said only if the data's p-value supports it.
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
  const v = (key: string) => N?.n[key] ?? NaN;
  const mightBeChance = $derived(v('gender.woman_director_films.p') > 0.05);

  // the films, from films.json, in each list's own rank order
  const byWomen = $derived(films.filter((f) => f.grp !== 'lb500' && f.wd === 1));
  const onImdb = $derived(byWomen.filter((f) => f.ir !== undefined).sort((a, b) => a.ir! - b.ir!));
  const onLb = $derived(byWomen.filter((f) => f.lr !== undefined && f.lr <= 250).sort((a, b) => a.lr! - b.lr!));
  const who = (f: Film) => {
    const women = f.wdn ?? [];
    const others = f.d.filter((d) => !women.includes(d));
    const names = (xs: string[]) => xs.join(' and ');
    return others.length ? `${names(women)}, with ${names(others)}` : names(women);
  };

  const IDS = ['all', 'women', 'on-imdb', 'on-letterboxd', 'credits', 'end'];
  const steps = $derived.by((): StageStep[] => {
    const base = byGroup(byId), p = palette();
    const faint: DotStyle = { fill: p.faint, alpha: 0.85 };
    const film = (k: string) => byId.get(parseKey(k).id ?? '');
    const women = (k: string) => (film(k)?.wd === 1 ? base(k) : faint);
    const keys = lay?.keys ?? [];
    const wk = keys.filter((k) => film(k)?.wd === 1);
    const films_: [string, string] = [n('gender.woman_director_films.imdb.n'), n('gender.woman_director_films.lb.n')];
    return [
      { view: {}, style: base },
      { view: { keys: wk, pad: 30, maxK: 2.6, alignTop: true }, style: women, stat: films_ },
      { view: { keys: wk.filter((k) => k.endsWith(':i')), pad: 30, maxK: 3.2, alignTop: true }, style: women, stat: films_ },
      { view: { keys: wk.filter((k) => k.endsWith(':l')), pad: 30, maxK: 3.2, alignTop: true }, style: women, stat: films_ },
      { view: {}, style: women, stat: [n('gender.director_credits.imdb.women'), n('gender.director_credits.lb.women')] },
      { view: {}, style: women, stat: films_ }
    ];
  });

  onMount(async () => {
    try {
      const [f, nn, L1] = await Promise.all([loadFilms(), loadNumbers(), loadLayout('womendir.grid')]);
      films = f; N = nn; lay = L1;
    } catch (e) { error = String(e); }
  });
</script>

<svelte:head><title>Who’s behind the camera · Quantifying Taste</title><meta name="description" content="How many films on IMDb’s and Letterboxd’s Top 250s were directed by women." /><meta property="og:title" content="Who’s behind the camera · Quantifying Taste" /><meta property="og:description" content="How many films on IMDb’s and Letterboxd’s Top 250s were directed by women." /><meta property="og:type" content="article" /><link rel="preload" href="{base}/data/layouts/womendir.grid.json" as="fetch" crossorigin="anonymous" /></svelte:head>

<header class="story-top">
  <a href="../">Quantifying Taste</a>
</header>

<BeatOpener beat={4} label="Who’s behind the camera" title="Few films on either list were directed by women" dek="Letterboxd’s list includes a few more than IMDb’s, but only a few: {n('gender.woman_director_films.distinct.n')} different films across both lists." />

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if N && lay && films.length}
  <Beat
    beat={4}
    layout={lay}
    {steps}
    ids={IDS}
    numbers={N}
    films={byId}
    summary="Chart: each list as a block of 250 dots, one per film, IMDb’s to the left of a centre line and Letterboxd’s to the right. Films a woman directed or co-directed sit in the top row of each block. The cards name every one of them."
  >
    {#snippet keyNote()}
      Each dot is one film on one list. Each list fills from the top, starting with the films a woman directed or
      co-directed. Director gender as recorded on Wikidata.
    {/snippet}
    {#snippet card(i)}
      {#if i === 0}
        <p>The same two lists, one dot per film, as two blocks of 250.</p>
        <p>This time the question is who directed each film.</p>
      {:else if i === 1}
        <h2 class="lead">Letterboxd’s list has a few more films directed by women</h2>
        <p>A woman directed or co-directed <strong>{n('gender.woman_director_films.imdb.n')}</strong> of IMDb’s 250 films ({n('gender.woman_director_films.imdb.pct')}%) and <strong>{n('gender.woman_director_films.lb.n')}</strong> of Letterboxd’s ({n('gender.woman_director_films.lb.pct')}%).</p>
      {:else if i === 2}
        <h2 class="lead"><span class="sw imdb" aria-hidden="true"></span>On IMDb’s list</h2>
        <ul class="films">
          {#each onImdb as f}
            <li>
              <span class="rank">#{f.ir}</span>
              <span class="film"><span class="t">{f.t}</span> <span class="y">{f.y}</span></span>
              <span class="who">{who(f)}</span>
              {#if f.grp === 'both'}<span class="both"><span class="dot" aria-hidden="true"></span>Also on Letterboxd’s list</span>{/if}
            </li>
          {/each}
        </ul>
      {:else if i === 3}
        <h2 class="lead"><span class="sw lb" aria-hidden="true"></span>On Letterboxd’s list</h2>
        <ul class="films">
          {#each onLb as f}
            <li>
              <span class="rank">#{f.lr}</span>
              <span class="film"><span class="t">{f.t}</span> <span class="y">{f.y}</span></span>
              <span class="who">{who(f)}</span>
              {#if f.grp === 'both'}<span class="both"><span class="dot" aria-hidden="true"></span>Also on IMDb’s list</span>{/if}
            </li>
          {/each}
        </ul>
      {:else if i === 4}
        <h2 class="lead">Counting every director credit</h2>
        <p>Across IMDb’s list, <strong>{n('gender.director_credits.imdb.women')}</strong> of the director credits go to women and {n('gender.director_credits.imdb.men')} to men. Across Letterboxd’s, <strong>{n('gender.director_credits.lb.women')}</strong> go to women and {n('gender.director_credits.lb.men')} to men.</p>
        {#if mightBeChance}<p class="aside">Letterboxd’s crowd does reach a little further, but the counts are small enough that the gap could be down to chance.</p>{/if}
      {:else}
        <p>On countries, languages and directors, the two lists pull apart. Here they mostly agree: women directors are rare on both, and slightly less rare on Letterboxd’s.</p>
        <p class="aside">Both lists draw on a film history in which, for most of the last century, few women were given the chance to direct. The lists reflect that history as much as either crowd’s taste.</p>
      {/if}
    {/snippet}
    {#snippet next()}
      <NextLink href="../disagreements/" small="Next · 5 of 6" q="Where do they disagree most?" arrow="→" />
    {/snippet}
  </Beat>

{:else}
  <p class="col muted">Loading…</p>
{/if}

<style>
  /* a dot in the list's colour before the heading, like the Key's swatches, tying the list to the lit dots above */
  .sw { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 8px; vertical-align: 0.06em; }
  .sw.imdb { background: var(--imdb); box-shadow: inset 0 0 0 1px var(--imdb-edge); }
  .sw.lb { background: var(--lb); }
  /* one entry per film: its rank on that list in a narrow column, then title and year, the director underneath,
     and a small "also on the other list" tag; thin rules between entries */
  .films { list-style: none; margin: 4px 0 0; padding: 0; }
  .films li {
    display: grid; grid-template-columns: 3.2em 1fr; column-gap: 8px; row-gap: 2px; align-items: baseline;
    padding: 10px 0; border-top: 1px solid var(--grid);
  }
  .films li:first-child { border-top: 0; padding-top: 2px; }
  .films li:last-child { padding-bottom: 0; }
  .rank { grid-row: 1 / span 3; font: 600 14px var(--sans); color: var(--muted); font-variant-numeric: tabular-nums; }
  .film { grid-column: 2; line-height: 1.3; }
  .t { font-weight: 600; }
  .y { color: var(--muted); font-size: 14px; font-variant-numeric: tabular-nums; }
  .who { grid-column: 2; color: var(--muted); font-size: 14px; line-height: 1.35; }
  .both { grid-column: 2; display: inline-flex; align-items: center; gap: 6px; margin-top: 4px; font: 500 12px var(--sans); color: var(--both-ink); }
  .both .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--both); flex: none; }
</style>

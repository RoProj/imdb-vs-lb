<!--
  Beat 2 of the guided story: "Where the films come from".
  The scroll machinery lives in Beat.svelte; this page supplies the steps (view + colouring) and the card text.
  Every number comes from numbers.json or films.json.
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
  const pct = (k: string) => `${n(k)}%`;

  // the film that introduces the unit: one dot is one film on one list
  const UNIT = 'tt0047478'; // Seven Samurai: Japanese, on both lists
  const unit = $derived(byId.get(UNIT));
  const EUROPE = ['Iran', 'Sweden', 'Russia', 'Italy', 'France'];
  const IDS = ['one-film', 'all', 'us', 'uk', 'europe', 'japan', 'language', 'end'];

  const steps = $derived.by((): StageStep[] => {
    const base = byGroup(byId), p = palette();
    const rows = (lay?.rows as string[] | undefined) ?? [];
    const rowOf = (f: Film) => (rows.includes(f.c) ? f.c : 'Other countries');
    const film = (key: string) => byId.get(parseKey(key).id ?? '');
    const faint: DotStyle = { fill: p.faint, alpha: 0.85 };
    // landmarks: each side's highest-ranked film in a single focused country, labelled right on the chart
    const short = (t: string) => { const m = t.length > 22 ? t.split(':')[0] : t; return m.length > 24 ? `${m.slice(0, 22).trimEnd()}…` : m; };
    // phones: a long title drops its leading "The" (The Shawshank Redemption → Shawshank Redemption)
    const narrowTitle = (t: string) => { const s = short(t); return s.length > 20 && s.startsWith('The ') ? s.slice(4) : undefined; };
    const landmarks = (names: string[]) => {
      if (names.length !== 1) return [];
      const inRow = films.filter((f) => f.grp !== 'lb500' && rowOf(f) === names[0]);
      const bi = inRow.filter((f) => f.ir).sort((a, b) => a.ir! - b.ir!)[0];
      const bl = inRow.filter((f) => f.lr && f.lr <= 250).sort((a, b) => a.lr! - b.lr!)[0];
      return [
        ...(bi ? [{ key: `${bi.id}:i`, title: short(bi.t), titleNarrow: narrowTitle(bi.t), text: `IMDb #${bi.ir}`, dx: -34, dy: -62 }] : []),
        ...(bl ? [{ key: `${bl.id}:l`, title: short(bl.t), titleNarrow: narrowTitle(bl.t), text: `Letterboxd #${bl.lr}`, dx: 34, dy: -62 }] : [])
      ];
    };
    const focus = (names: string[], stat?: [string, string]): StageStep => ({
      view: { rows: names }, focusRows: names, stat, notes: landmarks(names),
      style: (k) => { const f = film(k); return f && names.includes(rowOf(f)) ? base(k) : faint; }
    });
    const all: StageStep = { view: {}, style: base };
    const pair = (k: string): [string, string] => [n(`${k}.imdb.n`), n(`${k}.lb.n`)];
    return [
      {
        view: { keys: [`${UNIT}:i`, `${UNIT}:l`], pad: 30, maxK: 4.5 }, decoAlpha: 0,
        style: (k) => (parseKey(k).id === UNIT ? base(k) : { ...base(k), alpha: 0 }),
        notes: unit ? [
          { key: `${UNIT}:i`, title: 'Seven Samurai', text: `IMDb #${unit.ir}`, dx: -46, dy: -34 },
          { key: `${UNIT}:l`, title: 'Seven Samurai', text: `Letterboxd #${unit.lr}`, dx: 46, dy: -34 }
        ] : []
      },
      { ...all, stat: [n('lists.size'), n('lists.size')] },
      focus(['United States'], pair('country.us')),
      focus(['United Kingdom'], pair('country.uk')),
      focus(EUROPE),
      focus(['Japan'], pair('country.japan')),
      { view: {}, style: (k) => (film(k)?.l === 'English' ? base(k) : faint), stat: [`${n('language.english.imdb.pct')}%`, `${n('language.english.lb.pct')}%`] },
      all
    ];
  });

  onMount(async () => {
    try {
      const [f, nn, L1] = await Promise.all([loadFilms(), loadNumbers(), loadLayout('country.lean')]);
      films = f; N = nn; lay = L1;
    } catch (e) { error = String(e); }
  });
</script>

<svelte:head><title>Where the films come from · Quantifying Taste</title><meta name="description" content="Where the films on IMDb’s and Letterboxd’s Top 250s come from, and which way each country leans." /><meta property="og:title" content="Where the films come from · Quantifying Taste" /><meta property="og:description" content="Where the films on IMDb’s and Letterboxd’s Top 250s come from, and which way each country leans." /><meta property="og:type" content="article" /><link rel="preload" href="{base}/data/layouts/country.lean.json" as="fetch" crossorigin="anonymous" /></svelte:head>

<header class="story-top">
  <a href="../">Quantifying Taste</a>
</header>

<BeatOpener beat={2} label="Where the films come from" title="Each country leans toward one list" dek="Both lists are dominated by a handful of countries. But not the same handful, and not in the same amounts." />

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if N && lay && unit}
  <Beat
    layout={lay}
    {steps}
    ids={IDS}
    numbers={N}
    films={byId}
    summary="Chart: every film on each list as a dot, grouped by the film’s country, IMDb’s films to the left of a centre line and Letterboxd’s to the right. The cards describe what each step shows."
  >
    {#snippet keyNote()}
      Each dot is one film on one list, placed by its country (the first production country IMDb lists).
      Films on both lists sit next to the centre line, on both sides.
    {/snippet}
    {#snippet card(i)}
      {#if i === 0}
        <p>This is <em>{unit.t}</em> ({unit.y}), from {unit.c}. It is on both lists: #{unit.ir} on IMDb and #{unit.lr} on Letterboxd.</p>
        <p>So it gets two dots, one on each side of a line. Grey means a film is on both lists.</p>
      {:else if i === 1}
        <p>Here are all {n('lists.size')} films from each list, grouped by country. IMDb’s films grow to the left, Letterboxd’s to the right.</p>
        <p>The rows run from the country that leans most toward IMDb, at the top, to the one that leans most toward Letterboxd.</p>
      {:else if i === 2}
        <h2 class="lead">The United States fills both lists, but not equally</h2>
        <p><strong>{n('country.us.imdb.n')}</strong> of IMDb’s films are American ({pct('country.us.imdb.pct')}). On Letterboxd it’s <strong>{n('country.us.lb.n')}</strong> ({pct('country.us.lb.pct')}).</p>
      {:else if i === 3}
        <h2 class="lead">The United Kingdom leans the same way</h2>
        <p><strong>{n('country.uk.imdb.n')}</strong> British films on IMDb’s list, <strong>{n('country.uk.lb.n')}</strong> on Letterboxd’s.</p>
      {:else if i === 4}
        <h2 class="lead">Further from Hollywood, the balance tips</h2>
        <p>Every one of these countries has more films on Letterboxd’s list than on IMDb’s.</p>
        <table class="mini">
          <thead><tr><th scope="col">Country</th><th scope="col" class="imdb"><span>IMDb</span></th><th scope="col" class="lb"><span>Letterboxd</span></th></tr></thead>
          <tbody>
            {#each [['France', 'france'], ['Italy', 'italy'], ['Russia', 'russia'], ['Sweden', 'sweden'], ['Iran', 'iran']] as [name, key]}
              <tr><th scope="row">{name}</th><td>{n(`country.${key}.imdb.n`)}</td><td>{n(`country.${key}.lb.n`)}</td></tr>
            {/each}
          </tbody>
        </table>
      {:else if i === 5}
        <h2 class="lead">Japan swings furthest</h2>
        <p><strong>{n('country.japan.imdb.n')}</strong> Japanese films on IMDb’s list. <strong>{n('country.japan.lb.n')}</strong> on Letterboxd’s, {pct('country.japan.lb.pct')} of the whole list. No other country gains as much on Letterboxd’s list.</p>
      {:else if i === 6}
        <h2 class="lead">The same split shows up in language</h2>
        <p>The bold dots are films in English: <strong>{pct('language.english.imdb.pct')}</strong> of IMDb’s list, against <strong>{pct('language.english.lb.pct')}</strong> of Letterboxd’s.</p>
      {:else}
        <p>One list is mostly American and mostly in English. The other reaches further abroad, above all to Japan and Europe.</p>
        <p class="aside">The lists can’t tell us who their voters are. They do suggest two crowds looking in different directions.</p>
      {/if}
    {/snippet}
    {#snippet next()}
      <NextLink href="../directors/" small="Next · 3 of 6" q="Who does each crowd call a master?" arrow="→" />
    {/snippet}
  </Beat>

{:else}
  <p class="col muted">Loading…</p>
{/if}

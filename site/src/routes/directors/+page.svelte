<!--
  Beat 3 of the guided story: "Who each crowd calls a master".
  Same structure as the countries beat: one row per director (everyone with at least four films on either list),
  IMDb's films left of a centre line, Letterboxd's right, films on both lists next to the line.
  It opens by asking the reader to guess before anything is shown.
  Every number comes from numbers.json or films.json; claims like "more than any other director" are checked against
  the data at run time and the sentence is dropped if the data ever stops supporting it.
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

  // ---------------------------------------------------------------- the directors, straight from the data
  type Dir = { name: string; key: string; imdb: number; lb: number; lean: number };
  const dirs = $derived.by((): Dir[] => {
    if (!N || !lay) return [];
    const names = lay.rows as string[], keys = lay.rowkeys as string[];
    return names.map((name, i) => {
      const imdb = N!.n[`director.${keys[i]}.imdb`], lb = N!.n[`director.${keys[i]}.lb`];
      return { name, key: keys[i], imdb, lb, lean: lb - imdb };
    });
  });
  const d = (name: string) => dirs.find((x) => x.name === name);
  const dn = (name: string, side: 'imdb' | 'lb') => { const x = d(name); return x ? n(`director.${x.key}.${side}`) : ''; };
  const imdbSide = $derived(dirs.filter((x) => x.lean <= -3));
  const lbSide = $derived(dirs.filter((x) => x.lean >= 3));
  const noneOnImdb = $derived(dirs.filter((x) => x.imdb === 0));
  // claims, checked against the data
  const nolanMost = $derived.by(() => { const top = Math.max(...dirs.map((x) => x.imdb)); return d('Christopher Nolan')?.imdb === top && dirs.filter((x) => x.imdb === top).length === 1; });
  const kurosawaMost = $derived.by(() => { const top = Math.max(...dirs.map((x) => x.imdb + x.lb)); const k = d('Akira Kurosawa'); return !!k && k.imdb + k.lb === top && dirs.filter((x) => x.imdb + x.lb === top).length === 1; });
  const list = (xs: Dir[]) => xs.map((x) => x.name.split(' ').slice(-1)[0]).join(', ').replace(/, ([^,]*)$/, ' and $1');

  // ---------------------------------------------------------------- the guess
  const ASK = 'Martin Scorsese';
  let guess = $state<'imdb' | 'lb' | 'same' | null>(null);
  const answer = $derived.by(() => { const x = d(ASK); return !x ? null : x.imdb > x.lb ? 'imdb' : x.lb > x.imdb ? 'lb' : 'same'; });
  const SAY = { imdb: 'IMDb’s', lb: 'Letterboxd’s', same: 'About the same' } as const;

  const IDS = ['guess', 'all', 'hollywood', 'nolan', 'abroad', 'none-on-imdb', 'kurosawa', 'end'];
  const steps = $derived.by((): StageStep[] => {
    const base = byGroup(byId), p = palette();
    const faint: DotStyle = { fill: p.faint, alpha: 0.85 };
    const rowOf = (k: string) => parseKey(k).director ?? '';
    // landmarks: a single focused director's highest-ranked film on each list, labelled on the chart
    const short = (t: string) => { const m = t.length > 22 ? t.split(':')[0] : t; return m.length > 24 ? `${m.slice(0, 22).trimEnd()}…` : m; };
    const landmarks = (names: string[]) => {
      if (names.length !== 1) return [];
      const theirs = films.filter((f) => f.grp !== 'lb500' && f.d.includes(names[0]));
      const bi = theirs.filter((f) => f.ir).sort((a, b) => a.ir! - b.ir!)[0];
      const bl = theirs.filter((f) => f.lr && f.lr <= 250).sort((a, b) => a.lr! - b.lr!)[0];
      return [
        ...(bi ? [{ key: `s:${names[0]}|${bi.id}:i`, title: short(bi.t), text: `IMDb #${bi.ir}`, dx: -30, dy: -64 }] : []),
        ...(bl ? [{ key: `s:${names[0]}|${bl.id}:l`, title: short(bl.t), text: `Letterboxd #${bl.lr}`, dx: 30, dy: -64 }] : [])
      ];
    };
    const focus = (names: string[], frame = names, stat?: [string, string]): StageStep => ({
      view: { rows: frame, maxK: 2.6 }, focusRows: names, stat, notes: landmarks(names),
      style: (k) => (names.includes(rowOf(k)) ? base(k) : faint)
    });
    const all: StageStep = { view: {}, style: base };
    return [
      {
        view: { rows: [ASK], maxK: 2.8 }, focusRows: [ASK], hideCounts: !guess,
        stat: guess ? [dn(ASK, 'imdb'), dn(ASK, 'lb')] : undefined,
        style: (k) => (rowOf(k) === ASK && guess ? base(k) : { ...base(k), alpha: 0 })
      },
      all,
      focus(imdbSide.map((x) => x.name)),
      focus(['Christopher Nolan'], undefined, [dn('Christopher Nolan', 'imdb'), dn('Christopher Nolan', 'lb')]),
      focus(lbSide.map((x) => x.name)),
      focus(noneOnImdb.map((x) => x.name)),
      focus(['Akira Kurosawa'], undefined, [dn('Akira Kurosawa', 'imdb'), dn('Akira Kurosawa', 'lb')]),
      all
    ];
  });

  onMount(async () => {
    try {
      const [f, nn, L1] = await Promise.all([loadFilms(), loadNumbers(), loadLayout('directors.lean')]);
      films = f; N = nn; lay = L1;
    } catch (e) { error = String(e); }
  });
</script>

<svelte:head><title>Who each crowd calls a master · Quantifying Taste</title><meta name="description" content="Which directors each crowd calls a master: Hollywood’s big names on IMDb, international art cinema on Letterboxd." /><meta property="og:title" content="Who each crowd calls a master · Quantifying Taste" /><meta property="og:description" content="Which directors each crowd calls a master: Hollywood’s big names on IMDb, international art cinema on Letterboxd." /><meta property="og:type" content="article" /><link rel="preload" href="{base}/data/layouts/directors.lean.json" as="fetch" crossorigin="anonymous" /></svelte:head>

<header class="story-top">
  <a href="../">Quantifying Taste</a>
</header>

<BeatOpener beat={3} label="Who each crowd calls a master" title="Each list has its own masters" dek="A handful of directors turn up again and again. Which ones depends on which list you read." />

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if N && lay && dirs.length}
  <Beat
    visible={guess ? IDS.length : 1}
    beat={3}
    layout={lay}
    {steps}
    ids={IDS}
    numbers={N}
    films={byId}
    summary="Chart: one row for each director with at least four films on either list. Each of their films is a dot: IMDb’s list to the left of a centre line, Letterboxd’s to the right. The cards describe what each step shows."
  >
    {#snippet keyNote()}
      One row per director with at least four films on either list. Each dot is one of their films on one list;
      films on both lists sit next to the centre line, on both sides.
    {/snippet}
    {#snippet card(i)}
      {#if i === 0}
        <h2 class="lead">Before we look: a guess</h2>
        <p>Which list has more films by <strong>{ASK}</strong>?</p>
        <div class="choices" role="group" aria-label="Your guess">
          {#each ['imdb', 'lb', 'same'] as const as g}
            <button type="button" class="choice {g}" aria-pressed={guess === g} disabled={guess !== null && guess !== g}
              aria-disabled={guess !== null} onclick={() => { if (guess === null) guess = g; }}>{SAY[g]}</button>
          {/each}
        </div>
        <p class="reveal" aria-live="polite">
          {#if !guess}<span class="prompt">Pick one to see the answer and carry on.</span>{/if}
          {#if guess && answer}
            {guess === answer ? 'Right.' : 'Not quite.'}
            {answer === 'same' ? 'About the same' : `It’s ${SAY[answer]}`}: <strong>{dn(ASK, 'imdb')}</strong> of his films on IMDb’s list against <strong>{dn(ASK, 'lb')}</strong> on Letterboxd’s.
          {/if}
        </p>
      {:else if i === 1}
        <p>Here is every director with at least four films on either list. Same layout as before: IMDb’s films to the left of the line, Letterboxd’s to the right.</p>
        <p>The rows run from the director who leans most toward IMDb, at the top, to the one who leans most toward Letterboxd.</p>
      {:else if i === 2}
        <h2 class="lead">Hollywood’s best-known names lean IMDb</h2>
        <p class="phone-only">{list(imdbSide)}: every one has more films on IMDb’s list than on Letterboxd’s.</p>
        <table class="mini wide-only">
          <thead><tr><th scope="col">Director</th><th scope="col" class="imdb"><span>IMDb</span></th><th scope="col" class="lb"><span>Letterboxd</span></th></tr></thead>
          <tbody>
            {#each imdbSide as x}<tr><th scope="row">{x.name}</th><td>{n(`director.${x.key}.imdb`)}</td><td>{n(`director.${x.key}.lb`)}</td></tr>{/each}
          </tbody>
        </table>
      {:else if i === 3}
        <h2 class="lead">Christopher Nolan</h2>
        <p><strong>{dn('Christopher Nolan', 'imdb')}</strong> films on IMDb’s list{#if nolanMost}, more than any other director{/if}. Letterboxd’s list has <strong>{dn('Christopher Nolan', 'lb')}</strong>.</p>
        <p class="aside">Still a lot: both crowds like Nolan. IMDb’s just likes him more.</p>
      {:else if i === 4}
        <h2 class="lead">Letterboxd’s masters mostly worked outside the US</h2>
        <p class="phone-only">{list(lbSide)}: every one has more films on Letterboxd’s list than on IMDb’s.</p>
        <table class="mini wide-only">
          <thead><tr><th scope="col">Director</th><th scope="col" class="imdb"><span>IMDb</span></th><th scope="col" class="lb"><span>Letterboxd</span></th></tr></thead>
          <tbody>
            {#each lbSide as x}<tr><th scope="row">{x.name}</th><td>{n(`director.${x.key}.imdb`)}</td><td>{n(`director.${x.key}.lb`)}</td></tr>{/each}
          </tbody>
        </table>
        {#if d('Sidney Lumet')}<p class="aside">The exception is Sidney Lumet, an American, with {dn('Sidney Lumet', 'imdb')} film on IMDb’s list and {dn('Sidney Lumet', 'lb')} on Letterboxd’s.</p>{/if}
      {:else if i === 5}
        <h2 class="lead">Some don’t appear on IMDb’s list at all</h2>
        <p>{list(noneOnImdb)}: <strong>{noneOnImdb.length === 3 ? 'three' : noneOnImdb.length}</strong> directors with at least four films on Letterboxd’s list and none on IMDb’s.</p>
      {:else if i === 6}
        <h2 class="lead">The master both crowds share</h2>
        <p>Akira Kurosawa: <strong>{dn('Akira Kurosawa', 'imdb')}</strong> films on IMDb’s list and <strong>{dn('Akira Kurosawa', 'lb')}</strong> on Letterboxd’s{#if kurosawaMost}, more across both lists than any other director{/if}.</p>
      {:else}
        <p>IMDb’s list celebrates Hollywood’s big names. Letterboxd’s reaches for international art cinema.</p>
        <p class="aside">It’s the same split as the countries, seen through the people who made the films.</p>
      {/if}
    {/snippet}
    {#snippet next()}
      <NextLink href="../women-directors/" small="Next · 4 of 6" q="Who’s behind the camera?" arrow="→" />
    {/snippet}
  </Beat>

{:else}
  <p class="col muted">Loading…</p>
{/if}

<style>
  .choices { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 4px; }
  .choice {
    min-height: 44px; padding: 8px 16px; border-radius: 99px; border: 1.5px solid var(--line); background: var(--bg);
    font: 600 16px var(--sans); cursor: pointer; transition: background 0.15s, border-color 0.15s;
  }
  .choice:hover:not(:disabled):not([aria-disabled='true']) { border-color: var(--muted); }
  .choice[aria-disabled='true'] { cursor: default; }
  .choice:disabled { opacity: 0.4; }
  .prompt { font: 500 14px var(--sans); color: var(--muted); }
  .choice.imdb[aria-pressed='true'] { background: var(--imdb); border-color: var(--imdb-edge); }
  .choice.lb[aria-pressed='true'] { background: var(--lb); border-color: var(--lb-edge); color: var(--ink); }
  .choice.same[aria-pressed='true'] { background: var(--both); border-color: var(--both-edge); color: var(--ink); }
  .reveal { min-height: 1.5em; margin-top: 10px; }
  /* phones: the chart already shows each director's two counts, so the card names them instead of repeating a long table
     that would be taller than the reading area */
  .wide-only { display: none; }
  @media (min-width: 900px) { .wide-only { display: table; } .phone-only { display: none; } }
  @media (prefers-reduced-motion: reduce) { .choice { transition: none; } }
</style>

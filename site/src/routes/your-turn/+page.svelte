<!--
  After the story: "Your turn". Two small tools built only on the site's own data (films.json), so they work offline
  and every answer is one the data can back:
  1. Find your film: search any of the 579 films (both Top 250s, plus Letterboxd's 251 to 500) and see where each
     crowd ranks it. Films outside these lists get an honest "not on either list".
  2. Which list are you? Tap the films you love from sixteen and see which crowd your picks sit closer to. Always eight
     films only on IMDb's list and eight only on Letterboxd's (films on both can't tip the answer). The first set is the
     best known (most IMDb votes / most Letterboxd views); "Reshuffle" draws a fresh random eight of each from the
     better-known half of each list, so the films stay recognisable. It's a nudge, not a verdict, and the page says so.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { groupLabel, loadFilms, type Film } from '$lib/data';
  import BeatOpener from '$lib/story/BeatOpener.svelte';
  import NextLink from '$lib/story/NextLink.svelte';
  import FilmTip from '$lib/engine/FilmTip.svelte';
  import '$lib/story/story.css';

  let films = $state<Film[]>([]);
  let error = $state('');
  onMount(async () => {
    try { films = await loadFilms(); } catch (e) { error = String(e); }
  });

  // ------------------------------------------------------------------ find your film
  // search ignores case, accents, punctuation and a leading "The"
  const norm = (t: string) =>
    t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[’'`]/g, '').replace(/[^a-z0-9]+/g, ' ').trim().replace(/^the /, '');
  const index = $derived(films.map((f) => ({ f, keys: [f.t, ...(f.aka ?? [])].map(norm), pop: (f.iv ?? 0) + (f.lv ?? 0) })));

  let query = $state('');
  let open = $state(false);
  let activeIdx = $state(-1);
  let picked = $state<Film | null>(null);
  let inputEl = $state<HTMLInputElement>();

  const matches = $derived.by(() => {
    const q = norm(query);
    if (q.length < 2) return [];
    const scored: { f: Film; s: number; pop: number }[] = [];
    for (const { f, keys, pop } of index) {
      let s = 9;
      for (const k of keys) {
        if (k === q) s = Math.min(s, 0);
        else if (k.startsWith(q)) s = Math.min(s, 1);
        else if (k.split(' ').some((w) => w.startsWith(q))) s = Math.min(s, 2);
        else if (k.includes(q)) s = Math.min(s, 3);
      }
      if (s < 9) scored.push({ f, s, pop });
    }
    return scored.sort((a, b) => a.s - b.s || b.pop - a.pop).slice(0, 6).map((x) => x.f);
  });
  const noMatch = $derived(norm(query).length >= 2 && !matches.length);

  function choose(f: Film) {
    picked = f;
    query = f.t;
    open = false;
    activeIdx = -1;
  }
  function onKey(e: KeyboardEvent) {
    if (!matches.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); open = true; activeIdx = (activeIdx + 1) % matches.length; }
    else if (e.key === 'ArrowUp') { e.preventDefault(); open = true; activeIdx = (activeIdx - 1 + matches.length) % matches.length; }
    else if (e.key === 'Enter') { e.preventDefault(); choose(matches[Math.max(0, activeIdx)]); }
    else if (e.key === 'Escape') { open = false; activeIdx = -1; }
  }
  // a "Try" pill fills the search and shows the answer (the result is announced by its live region)
  function tryFilm(title: string) {
    const f = films.find((x) => x.t === title);
    if (f) choose(f);
  }
  // a few to try, taken from the data so they always exist: the film each list puts first, plus Inception
  const tries = $derived.by(() => {
    const i1 = films.find((f) => f.ir === 1), l1 = films.find((f) => f.lr === 1), inc = films.find((f) => f.t === 'Inception');
    return [i1, l1, inc].filter((f): f is Film => !!f);
  });

  // the same wording as the chart's Key
  const lists = (f: Film) => groupLabel[f.grp];

  // the verdict, from ranks only (each crowd's ratings run on its own scale, so they aren't compared directly)
  const verdict = $derived.by(() => {
    const f = picked;
    if (!f) return null;
    if (f.grp === 'both') {
      const d = f.lr! - f.ir!;
      if (Math.abs(d) <= 10) return { side: 'both', head: 'Both crowds rank it about the same', sub: `#${f.ir} on IMDb’s list, #${f.lr} on Letterboxd’s.` };
      return d > 0
        ? { side: 'imdb', head: 'IMDb’s crowd ranks it higher', sub: `#${f.ir} on IMDb’s list, #${f.lr} on Letterboxd’s.` }
        : { side: 'lb', head: 'Letterboxd’s crowd ranks it higher', sub: `#${f.lr} on Letterboxd’s list, #${f.ir} on IMDb’s.` };
    }
    if (f.grp === 'imdb')
      return { side: 'imdb', head: 'Only IMDb’s crowd puts it in their Top 250', sub: f.lr ? `#${f.ir} on IMDb’s list. Letterboxd has it at #${f.lr}, outside its Top 250.` : `#${f.ir} on IMDb’s list. It isn’t in Letterboxd’s Top 500.` };
    if (f.grp === 'lb')
      return { side: 'lb', head: 'Only Letterboxd’s crowd puts it in their Top 250', sub: `#${f.lr} on Letterboxd’s list. It isn’t on IMDb’s Top 250.` };
    return { side: 'none', head: 'Neither Top 250 has it', sub: `Letterboxd ranks it #${f.lr}, just outside its Top 250. It isn’t on IMDb’s list.` };
  });

  // ------------------------------------------------------------------ which list are you?
  const QUIZ_EACH = 8;
  // each list's own films (not on the other's Top 250), best known first
  const imdbPool = $derived(films.filter((f) => f.grp === 'imdb').sort((a, b) => (b.iv ?? 0) - (a.iv ?? 0)));
  const lbPool = $derived(films.filter((f) => f.grp === 'lb').sort((a, b) => (b.lv ?? 0) - (a.lv ?? 0)));
  let draw = $state(0); // 0 = the best-known set; each "Reshuffle" press draws a fresh random set
  const shuffle = <T,>(xs: T[]) => { const a = [...xs]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const quiz = $derived.by(() => {
    void draw;
    let imdb: Film[], lb: Film[];
    if (draw === 0) { imdb = imdbPool.slice(0, QUIZ_EACH); lb = lbPool.slice(0, QUIZ_EACH); }
    else {
      // the better-known half of each list, so a random draw is still films people are likely to have seen
      imdb = shuffle(imdbPool.slice(0, Math.ceil(imdbPool.length / 2))).slice(0, QUIZ_EACH);
      lb = shuffle(lbPool.slice(0, Math.ceil(lbPool.length / 2))).slice(0, QUIZ_EACH);
    }
    const out: Film[] = [];
    for (let i = 0; i < QUIZ_EACH; i++) { if (i % 2) { out.push(lb[i], imdb[i]); } else { out.push(imdb[i], lb[i]); } }
    const set = out.filter(Boolean);
    return draw === 0 ? set : shuffle(set);
  });
  function newFilms() { loved = new Set(); draw++; }
  let loved = $state<Set<string>>(new Set());
  function toggle(id: string) {
    const s = new Set(loved);
    if (s.has(id)) s.delete(id); else s.add(id);
    loved = s;
  }
  const tally = $derived.by(() => {
    let i = 0, l = 0;
    for (const f of quiz) if (loved.has(f.id)) { if (f.grp === 'imdb') i++; else l++; }
    return { i, l, n: i + l };
  });
  const MIN_PICKS = 3;
  const result = $derived.by(() => {
    const { i, l, n } = tally;
    if (n < MIN_PICKS) return null;
    const d = l - i;
    const head = d >= 2 ? 'Your taste sits closer to Letterboxd’s crowd' : d <= -2 ? 'Your taste sits closer to IMDb’s crowd' : 'You sit right between the two crowds';
    return { head, pos: l / n };
  });
</script>

<svelte:head>
  <title>Your turn · Quantifying Taste</title>
  <meta name="description" content="Find any film on IMDb’s or Letterboxd’s Top 250 and see which crowd ranks it higher, then find out which list your taste sits closer to." />
  <meta property="og:title" content="Your turn · Quantifying Taste" />
  <meta property="og:description" content="Find any film on IMDb’s or Letterboxd’s Top 250 and see which crowd ranks it higher, then find out which list your taste sits closer to." />
  <meta property="og:type" content="article" />
</svelte:head>

<header class="story-top">
  <a href="../">Quantifying Taste</a>
</header>

<BeatOpener compact beat={6} label="Your turn" title="Where does your favourite land?" dek="Look up any film on either list, then find out which crowd your taste sits closer to." />

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if films.length}
  <div class="col turn">
    <!-- 1. find your film -->
    <section class="card" aria-labelledby="find-h">
      <h2 class="lead" id="find-h">Find your film</h2>
      <p class="hint">Any film on either Top 250, or in Letterboxd’s 251 to 500.</p>

      <div class="search">
        <label class="sr-only" for="film-q">Search for a film</label>
        <input
          id="film-q" bind:this={inputEl} type="search" autocomplete="off" spellcheck="false" placeholder="Search a title, e.g. Spirited Away"
          role="combobox" aria-expanded={open && matches.length > 0} aria-controls="film-list" aria-autocomplete="list"
          aria-activedescendant={open && activeIdx >= 0 ? `film-opt-${activeIdx}` : undefined}
          bind:value={query}
          oninput={() => { open = true; activeIdx = -1; }}
          onfocus={() => (open = true)}
          onblur={() => setTimeout(() => (open = false), 120)}
          onkeydown={onKey}
        />
        {#if open && matches.length}
          <ul class="options" id="film-list" role="listbox" aria-label="Matching films">
            {#each matches as f, i}
              <li id="film-opt-{i}" role="option" aria-selected={i === activeIdx} class:active={i === activeIdx}
                onpointerdown={(e) => { e.preventDefault(); choose(f); }}>
                <span class="o-title">{f.t}</span> <span class="o-year">{f.y}</span>
                <span class="o-list">{lists(f)}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      {#if !picked && !query}
        <div class="tries"><span class="tries-l">Try</span>
          {#each tries as f}<button type="button" class="try" onclick={() => tryFilm(f.t)}>{f.t}</button>{/each}
        </div>
      {/if}

      <div aria-live="polite">
        {#if noMatch}
          <p class="none">That film isn’t on either Top 250, or in Letterboxd’s 251 to 500, so there’s nothing to compare. Check the spelling, or try another.</p>
        {:else if picked && verdict && query === picked.t}
          <div class="result">
            <p class="verdict {verdict.side}"><span class="sw" aria-hidden="true"></span>{verdict.head}</p>
            <p class="sub">{verdict.sub}</p>
            <div class="tip"><FilmTip film={picked} compareLine={false} /></div>
            <p class="fine">Ratings: IMDb’s out of 10; Letterboxd’s five stars doubled to 10. The verdict uses ranks only, since each crowd rates on its own habits.</p>
          </div>
        {/if}
      </div>
    </section>

    <!-- 2. which list are you? -->
    <section class="card" aria-labelledby="quiz-h">
      <div class="quiz-head">
        <h2 class="lead" id="quiz-h">Which list are you?</h2>
        <button type="button" class="refresh" onclick={newFilms}>
          <!-- Material Icons "shuffle" (Google, Apache 2.0) -->
          <svg class="r-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M10.59 9.17 5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z" /></svg>
          Reshuffle
        </button>
      </div>
      <p class="hint">Tap the films you love. Each one is on only one of the two lists. Sixteen films is a small sample, so take the answer as a nudge, not a verdict.</p>
      <ul class="picks">
        {#each quiz as f}
          <li>
            <button type="button" class="pick" class:on={loved.has(f.id)} aria-pressed={loved.has(f.id)} onclick={() => toggle(f.id)}>
              <span class="check" aria-hidden="true"></span>
              <span class="p-title">{f.t}</span> <span class="p-year">{f.y}</span>
            </button>
          </li>
        {/each}
      </ul>

      <div class="meter-wrap" aria-live="polite">
        {#if result}
          <p class="verdict">{result.head}</p>
          <div class="meter" aria-hidden="true">
            <span class="end imdb">IMDb</span>
            <span class="bar"><span class="mark" style:left="{result.pos * 100}%"></span></span>
            <span class="end lb">Letterboxd</span>
          </div>
          <p class="sub">You picked <strong>{tally.i}</strong> from IMDb’s list and <strong>{tally.l}</strong> from Letterboxd’s.
            <button type="button" class="clear" onclick={() => (loved = new Set())}>Clear picks</button></p>
        {:else}
          <p class="sub">Pick at least {MIN_PICKS} to see where you land{tally.n ? ` (${tally.n} so far)` : ''}.</p>
        {/if}
      </div>
    </section>

    <div class="end-link">
      <NextLink href="../" small="The end" q="Start the story again" arrow="↺" />
    </div>
  </div>
{:else}
  <p class="col muted">Loading…</p>
{/if}

<style>
  .turn { display: grid; gap: 28px; padding-bottom: 12vh; }
  /* the same caption card as the story */
  .card {
    background: var(--surface); border: 1.5px dotted var(--muted); border-radius: 10px; padding: 16px 18px;
    font: 16px/1.6 var(--sans); color: var(--ink);
  }
  @media (min-width: 900px) { .card { padding: 22px 24px; font-size: 18px; } }
  .lead { font: 650 19px/1.3 var(--sans); letter-spacing: -0.01em; margin: 0 0 6px; }
  @media (min-width: 900px) { .lead { font-size: 21px; } }
  .hint { color: var(--muted); font-size: 14px; margin: 0 0 14px; }

  /* search */
  .search { position: relative; }
  input[type='search'] {
    width: 100%; min-height: 48px; padding: 10px 14px; font: 16px var(--sans); color: var(--ink);
    background: var(--bg); border: 1.5px solid var(--line); border-radius: 10px; box-sizing: border-box;
  }
  input[type='search']:focus { outline: 2px solid var(--lb-tag); outline-offset: 1px; border-color: transparent; }
  .options {
    position: absolute; z-index: 5; left: 0; right: 0; top: calc(100% + 6px); margin: 0; padding: 6px; list-style: none;
    background: var(--surface); border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 10px 30px rgba(31, 30, 27, 0.12);
  }
  .options li {
    display: grid; grid-template-columns: 1fr auto; column-gap: 10px; align-items: baseline; padding: 10px 10px; min-height: 44px;
    box-sizing: border-box; border-radius: 7px; cursor: pointer; font-size: 16px; line-height: 1.3;
  }
  .options li.active, .options li:hover { background: var(--grid); }
  .o-title { font-weight: 600; }
  .o-year { color: var(--muted); font-size: 14px; }
  .o-list { grid-column: 1 / -1; color: var(--muted); font-size: 12px; }
  .tries { margin: 12px 0 0; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .tries-l { font-size: 14px; color: var(--muted); margin-right: 2px; }
  .try {
    min-height: 44px; padding: 0 14px; border-radius: 99px; border: 1px solid var(--line); background: transparent;
    font: 600 14px var(--sans); color: var(--ink); cursor: pointer;
  }
  .try:hover { border-color: var(--muted); }
  .none { margin: 14px 0 0; font-size: 14px; color: var(--muted); }

  /* result */
  .result { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--grid); }
  .verdict { font: 650 16px/1.35 var(--sans); margin: 0; display: flex; align-items: center; gap: 8px; }
  @media (min-width: 900px) { .verdict { font-size: 18px; } }
  .verdict .sw { width: 11px; height: 11px; border-radius: 50%; flex: none; background: var(--both); }
  .verdict.imdb .sw { background: var(--imdb); box-shadow: inset 0 0 0 1px var(--imdb-edge); }
  .verdict.lb .sw { background: var(--lb); }
  .verdict.none .sw { background: var(--line); }
  .sub { color: var(--muted); font-size: 14px; margin: 4px 0 0; line-height: 1.5; }
  .tip { margin-top: 14px; padding: 14px; border-radius: 10px; background: var(--bg); font-size: 14px; line-height: 1.4; }

  /* quiz */
  .picks { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr; gap: 8px; }
  @media (min-width: 560px) { .picks { grid-template-columns: 1fr 1fr; } }
  .pick {
    width: 100%; height: 100%; min-height: 48px; display: flex; align-items: center; gap: 10px; text-align: left; padding: 8px 12px;
    font: 15px/1.3 var(--sans); color: var(--ink); background: var(--bg); border: 1.5px solid var(--line); border-radius: 10px; cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  .pick:hover { border-color: var(--muted); }
  .pick.on { border-color: var(--ink); background: var(--surface); }
  .check {
    flex: none; width: 20px; height: 20px; border-radius: 50%; border: 1.5px solid var(--line); display: grid; place-items: center;
    font-size: 12px; font-weight: 700; color: var(--bg);
  }
  .pick.on .check { background: var(--ink); border-color: var(--ink); }
  .pick.on .check::before { content: '✓'; }
  .p-title { font-weight: 600; }
  .p-year { color: var(--muted); font-size: 14px; font-weight: 400; margin-left: auto; }
  /* phones: the films wrap as chips sized to their titles, so all sixteen fit in about one screen. Off = outlined,
     on = filled ink with a tick. The year is kept for screen readers but not shown (it costs a lot of width). */
  @media (max-width: 559px) {
    .picks { display: flex; flex-wrap: wrap; gap: 8px 6px; }
    .picks li { max-width: 100%; }
    .pick {
      width: auto; height: auto; max-width: 100%; min-height: 44px; gap: 5px; padding: 8px 13px; border-radius: 99px; font-size: 14px;
      background: transparent; transition: border-color 0.15s, background 0.15s, color 0.15s, padding 0.15s;
    }
    /* the mark keeps the same width on and off ("+" then "✓"), so tapping a chip never reflows the others */
    .pick { padding-left: 10px; }
    .pick .check { width: 12px; height: 16px; border: 0; background: none; color: var(--muted); font-size: 16px; font-weight: 500; line-height: 1; transform: translateY(-1px); }
    .pick .check::before { content: '+'; }
    .pick.on { background: var(--ink); border-color: var(--ink); color: var(--bg); }
    .pick.on .check { background: none; color: var(--bg); font-size: 13px; font-weight: 700; }
    .pick.on .check::before { content: '✓'; }
    .p-year { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  }
  /* the result stays pinned to the bottom of the screen while the quiz is on screen, so every tap shows its effect */
  .meter-wrap {
    position: sticky; bottom: 0; z-index: 2; margin: 18px -18px -16px; padding: 14px 18px 16px;
    background: var(--surface); border-top: 1px solid var(--grid); border-radius: 0 0 10px 10px;
    box-shadow: 0 -10px 20px -14px rgba(31, 30, 27, 0.25);
  }
  @media (min-width: 900px) { .meter-wrap { margin: 18px -24px -22px; padding: 16px 24px 22px; } }
  .meter { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; margin: 12px 0 4px; }
  .end { font: 650 12px var(--sans); letter-spacing: 0.06em; text-transform: uppercase; padding: 2px 7px; border-radius: 4px; }
  .end.imdb { background: var(--imdb-tag); color: var(--imdb-tag-ink); }
  .end.lb { background: var(--lb-tag); color: var(--lb-tag-ink); }
  .bar { position: relative; height: 6px; border-radius: 99px; background: linear-gradient(90deg, var(--imdb), var(--both), var(--lb)); }
  .mark {
    position: absolute; top: 50%; width: 16px; height: 16px; border-radius: 50%; transform: translate(-50%, -50%);
    background: var(--surface); border: 2.5px solid var(--ink); transition: left 0.4s cubic-bezier(0.65, 0, 0.35, 1);
  }
  @media (prefers-reduced-motion: reduce) { .mark, .pick { transition: none; } }
  .end-link { margin-top: 8px; }
  /* heading and Reshuffle share a row, centred on each other; the description gets room above and below */
  .quiz-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px 20px; margin-bottom: 14px; }
  .quiz-head h2 { margin: 0; }
  .quiz-head + .hint { line-height: 1.6; margin: 0 0 24px; max-width: 36em; }
  .refresh {
    flex: none; display: inline-flex; align-items: center; gap: 6px; min-height: 44px; padding: 0 16px 0 13px;
    border-radius: 99px; border: 1px solid var(--line); background: transparent; font: 600 14px var(--sans); color: var(--ink); cursor: pointer;
  }
  .refresh:hover { border-color: var(--muted); }
  .r-icon { display: block; flex: none; transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
  .refresh:hover .r-icon, .refresh:focus-visible .r-icon { transform: scaleX(-1); }
  .refresh:active .r-icon { transform: scaleX(-1) scale(0.85); }
  @media (prefers-reduced-motion: reduce) { .r-icon { transition: none; } }
  .fine { color: var(--muted); font-size: 12px; line-height: 1.5; margin: 10px 0 0; }
  .clear {
    display: inline-flex; align-items: center; min-height: 44px; vertical-align: middle;
    border: 0; background: none; padding: 0 0 0 6px; font: 600 14px var(--sans); color: var(--ink); cursor: pointer;
    text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 3px;
  }
  .clear:hover { text-decoration-color: var(--ink); }
</style>

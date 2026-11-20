<!--
  Beat 1 of the guided story: the hook, and the story's front page (the site root).
  Two arrangements of the same 500 dots: both lists side by side in rank order (hook.split), then sorted into
  three groups (hook.merge), where each shared film's two dots meet as one. The stage moves every dot between
  them as the reader scrolls. Every number comes from numbers.json or films.json.
-->
<script lang="ts">
  import { base } from '$app/paths';
  import { onMount } from 'svelte';
  import Beat from '$lib/story/Beat.svelte';
  import type { StageStep } from '$lib/story/StoryStage.svelte';
  import { loadFilms, loadLayout, loadNumbers, num, parseKey, type Film, type Layout, type Numbers } from '$lib/data';
  import { byGroup, byList } from '$lib/style';
  import BeatOpener from '$lib/story/BeatOpener.svelte';
  import NextLink from '$lib/story/NextLink.svelte';
  import HeroDots from '$lib/story/HeroDots.svelte';
  import ReadMore from '$lib/story/ReadMore.svelte';
  import '$lib/story/story.css';

  let films = $state<Film[]>([]);
  let N = $state<Numbers | null>(null);
  let split = $state<Layout | null>(null);
  let merge = $state<Layout | null>(null);
  let error = $state('');
  const byId = $derived(new Map(films.map((f) => [f.id, f])));
  const n = (key: string) => (N ? num(N, key) : '');
  // the date the lists were read, e.g. "13 November 2026"
  const collected = $derived(N?.meta?.collected
    ? new Date(`${N.meta.collected}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    : '');

  let hero = $state<HeroDots>();
  const INCEPTION = 'tt1375666';
  const inception = $derived(byId.get(INCEPTION));

  const IDS = ['inception', 'two-lists', 'shared', 'sorted', 'so-what'];
  const steps = $derived.by((): StageStep[] => {
    if (!merge) return [];
    const group = byGroup(byId);
    const all = merge.keys;
    return [
      {
        // the same framing as the next step, so when the other dots arrive they only fade in: nothing pans or zooms
        view: { keys: merge.keys, pad: 24, noPeek: true },
        stat: inception ? [`#${inception.ir}`, `#${inception.lr}`] : undefined,
        style: (k) => (parseKey(k).id === INCEPTION ? byList(k) : { ...byList(k), alpha: 0 }),
        notes: inception ? [
          { key: `${INCEPTION}:i`, title: 'Inception', text: `IMDb #${inception.ir}`, dx: -34, dy: 40 },
          { key: `${INCEPTION}:l`, title: 'Inception', text: `Letterboxd #${inception.lr}`, dx: 34, dy: -40 }
        ] : []
      },
      // frame the dots themselves (not the layout's empty margins), so the lists fill wide screens too
      { view: { keys: all, pad: 24 }, style: byList, stat: [n('lists.size'), n('lists.size')] },
      { view: { keys: all, pad: 24 }, style: group, stat: [n('overlap.both'), n('overlap.both')] },
      // three groups: the left/right side names fade out (the groups carry their own labels)
      { view: { keys: all, pad: 72 }, style: group, layout: merge, sides: false },
      { view: { keys: all, pad: 72 }, style: group, layout: merge, sides: false }
    ];
  });

  onMount(async () => {
    try {
      const [f, nn, L1, L2] = await Promise.all([loadFilms(), loadNumbers(), loadLayout('hook.split'), loadLayout('hook.merge')]);
      films = f; N = nn; split = L1; merge = L2;
    } catch (e) { error = String(e); }
  });
</script>

<svelte:head><title>Quantifying Taste</title><meta name="description" content="IMDb’s Top 250 and Letterboxd’s Top 250 share only 111 films. A data story about two crowds with different tastes." /><meta property="og:title" content="Quantifying Taste" /><meta property="og:description" content="IMDb’s Top 250 and Letterboxd’s Top 250 share only 111 films. A data story about two crowds with different tastes." /><meta property="og:type" content="article" /><link rel="preload" href="{base}/data/layouts/hook.split.json" as="fetch" crossorigin="anonymous" /><link rel="preload" href="{base}/data/layouts/hook.merge.json" as="fetch" crossorigin="anonymous" /></svelte:head>

<BeatOpener hero label="A data story" title="Quantifying Taste" dek={N ? `Two Top 250s. Only ${n('overlap.both')} films in common.` : ''}>
  {#if films.length}<HeroDots bind:this={hero} films={films.filter((f) => f.grp !== 'lb500')} />{/if}
  {#snippet intro()}
    {#if N}
      <ReadMore id="about">
        {#snippet teaser()}
          <p>IMDb and Letterboxd are both places where people rate the films they watch, and both keep a ranked list of the very best. This project sets those two lists side by side to see what each crowd values, and where they part ways.</p>
        {/snippet}
        <div class="about">
          <h2>What this is</h2>
          <p><em>Quantifying Taste</em> is a data story in six short pages. It compares IMDb’s Top {n('lists.size')} with the first {n('lists.size')} films of Letterboxd’s Top 500, and follows where they differ: where the films come from, who directed them, and the films one list loves that the other leaves out. The last page lets you look up a film yourself.</p>

          <h2>Why</h2>
          <p>IMDb began in 1990 as a film database and draws ratings from a very large, general audience. Letterboxd launched in 2011 as a social diary for logging films, and grew its own culture of reviews and lists. Both ask the same question of every film, so their top lists are a rare like-for-like look at two corners of internet film culture.</p>
          <p>The lists can’t say who the voters are, only what they chose. So every claim here is about the lists, and what they suggest.</p>

          <h2>How it was made</h2>
          <p>Both lists were read from the sites’ public pages on {collected}, one page at a time, and saved, so every number comes from the same snapshot. The charts are drawn from that data in your browser, and every number on these pages is generated from it and checked automatically against the source files before the site is built.</p>

          <h2>About the data</h2>
          <dl>
            <div><dt>The lists</dt><dd>IMDb’s Top {n('lists.size')}, and the first {n('lists.size')} of Letterboxd’s official Top 500. Films ranked 251–500 on Letterboxd appear only on the last two pages.</dd></div>
            <div><dt>Ranks and ratings</dt><dd>Each site’s own.</dd></div>
            <div><dt>Country, director, year</dt><dd>Taken from IMDb for both lists, so a film is labelled the same way on each.</dd></div>
            <div><dt>One country per film</dt><dd>The first production country IMDb lists, with older names mapped to today’s (West Germany counts as Germany).</dd></div>
            <div><dt>Women directors</dt><dd>Directors’ gender comes from Wikidata.</dd></div>
            <div><dt>Collected</dt><dd>{collected}. Both lists keep changing as people vote.</dd></div>
          </dl>

          <h2>What the lists can’t tell us</h2>
          <ul>
            <li><strong>Who the voters are.</strong> Neither site publishes who rates what, so the differences describe the lists, not the people.</li>
            <li><strong>Why a film ranks where it does.</strong> Each site builds its list with its own rules: minimum numbers of votes, weighting, and which kinds of film qualify.</li>
            <li><strong>Where a film was really made.</strong> One country per film is a simplification. Some US studio films shot in Britain, like <em>Inception</em> and <em>Gladiator</em>, count as British.</li>
          </ul>
          <p class="fine">Not affiliated with IMDb or Letterboxd.</p>
          <p class="credit">
            <span>© {new Date().getFullYear()} Rohan Projects</span>
            <a class="ig" href="https://www.instagram.com/ro1projects/" target="_blank" rel="noopener noreferrer" aria-label="Rohan Projects on Instagram, @ro1projects (opens in a new tab)">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4.2" /><circle cx="17.4" cy="6.6" r="0.6" fill="currentColor" stroke="none" /></svg>
              <span>@ro1projects</span>
            </a>
          </p>
        </div>
      </ReadMore>
    {/if}
  {/snippet}
  {#snippet actions()}
    <button type="button" class="replay" onclick={() => hero?.replay()}>Replay <span aria-hidden="true">↺</span></button>
  {/snippet}
</BeatOpener>

{#if error}
  <p class="col story-error">Could not load the data: {error}</p>
{:else if N && split && merge && inception}
  <Beat
    beat={1}
    layout={split}
    {steps}
    ids={IDS}
    numbers={N}
    films={byId}
    summary="Chart: every film on IMDb’s Top 250 and Letterboxd’s Top 250 as a dot, first as two blocks side by side in rank order, then sorted into films only on IMDb’s list, films on both, and films only on Letterboxd’s. The cards describe each step."
  >
    {#snippet keyNote()}
      Each dot is one film on one list. When the films are sorted, a film on both lists becomes a single grey dot in the middle.
    {/snippet}
    {#snippet card(i)}
      {#if i === 0}
        <h2 class="lead"><em>Inception</em> is #{inception.ir} on IMDb’s Top 250</h2>
        <p>On Letterboxd’s Top 250 it’s <strong>#{inception.lr}</strong>, nearly the last film on the list.</p>
      {:else if i === 1}
        <p>IMDb keeps a Top {n('lists.size')} of the films its users rate highest. Letterboxd keeps a Top 500 of its own; here we use its first {n('lists.size')}.</p>
        <p>Here are both, one dot per film, in rank order: IMDb’s on the left, Letterboxd’s on the right.</p>
      {:else if i === 2}
        <p>The grey dots are films that appear on both lists.</p>
      {:else if i === 3}
        <h2 class="lead">Only {n('overlap.both')} films are on both lists</h2>
        <p>Sort them out and fewer than half overlap. <strong>{n('overlap.imdb_only')}</strong> films are only on IMDb’s list, and <strong>{n('overlap.lb_only')}</strong> only on Letterboxd’s.</p>
      {:else}
        <p>Same kind of list, same {n('lists.size')} places, mostly different films.</p>
        <p>So what does each crowd choose? Start with where the films come from.</p>
      {/if}
    {/snippet}
    {#snippet next()}
      <NextLink href="./countries/" small="Next · 2 of 6" q="Where do the films come from?" arrow="→" />
    {/snippet}
  </Beat>

{:else}
  <p class="col muted">Loading…</p>
{/if}

<style>
  /* the front page's intro: the first two lines show, the rest opens under "Read more" */
  :global(.opener .intro p) { font: 400 16px/1.6 var(--sans); color: var(--ink); margin: 0 0 14px; }
  :global(.opener .intro .first p) { margin: 0; }
  .about { padding-top: 14px; }
  .about h2 { font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 28px 0 10px; }
  .about h2:first-child { margin-top: 10px; }
  .about dl { margin: 0 0 14px; display: grid; gap: 10px; }
  .about dl div { display: grid; grid-template-columns: 1fr; gap: 2px; }
  .about dt { font: 600 14px var(--sans); color: var(--ink); }
  .about dd { margin: 0; font: 400 16px/1.55 var(--sans); color: var(--ink); }
  .about ul { margin: 0 0 14px; padding-left: 1.1em; display: grid; gap: 10px; }
  .about li { font: 400 16px/1.55 var(--sans); }
  .about .fine { font-size: 14px !important; color: var(--muted) !important; margin-top: 20px !important; }
  /* the credit line: a hairline above, then "© year Rohan Projects", then the Instagram link (icon and handle together) */
  .about .credit {
    display: flex; flex-wrap: wrap; align-items: center; gap: 4px 16px; margin: 18px 0 6px !important;
    padding-top: 16px; border-top: 1px solid var(--line); font: 500 14px/1.4 var(--sans) !important; color: var(--muted) !important;
  }
  .ig {
    display: inline-flex; align-items: center; gap: 7px; min-height: 44px; color: var(--ink); text-decoration: none; border-radius: 6px;
  }
  .ig span { text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 4px; text-decoration-thickness: 1px; transition: text-decoration-color 160ms; }
  .ig svg { flex: none; transition: transform 200ms ease; }
  .ig:hover span { text-decoration-color: var(--ink); }
  .ig:hover svg { transform: scale(1.08); }
  .ig:focus-visible { outline: none; box-shadow: var(--focus); }
  @media (min-width: 900px) {
    :global(.opener .intro p), .about dd, .about li { font-size: 18px !important; }
    .about dl div { grid-template-columns: 11em 1fr; gap: 16px; }
    .about dt { padding-top: 3px; }
  }
  .replay {
    min-height: 44px; padding: 0 14px; border-radius: 99px; border: 1px solid var(--line); background: transparent;
    color: var(--ink); font: 600 14px var(--sans); cursor: pointer;
  }
  .replay:hover { border-color: var(--muted); }
</style>

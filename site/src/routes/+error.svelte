<!--
  Shown for any address the site doesn't have (GitHub Pages serves it as 404.html), and for any other error.
  Written like the rest of the site, with a way straight back into the story.
-->
<script lang="ts">
  import { page } from '$app/state';
  import { base } from '$app/paths';
  import NextLink from '$lib/story/NextLink.svelte';
  const missing = $derived(page.status === 404);
  const pages = [
    ['', 'Two Top 250s'],
    ['countries/', 'Where the films come from'],
    ['directors/', 'Who each crowd calls a master'],
    ['women-directors/', 'Who’s behind the camera'],
    ['disagreements/', 'Where they disagree most'],
    ['your-turn/', 'Your turn']
  ];
</script>

<svelte:head>
  <title>{missing ? 'Page not found' : 'Something went wrong'} · Quantifying Taste</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<main class="lost">
  <p class="kicker">{missing ? '404 · Page not found' : `Error ${page.status}`}</p>
  <h1>{missing ? 'This page isn’t on either list' : 'Something went wrong'}</h1>
  <p class="dek">
    {missing ? 'The address may be mistyped, or the page may have moved.' : 'Try reloading the page, or start the story again.'}
  </p>

  <div class="next"><NextLink href="{base}/" small="Start from the beginning" q="Two Top 250s" /></div>

  <nav aria-label="All pages">
    <h2>All six pages</h2>
    <ol>
      {#each pages as [path, title], i}
        <li><a href="{base}/{path}"><span class="n">{i + 1}</span>{title}</a></li>
      {/each}
    </ol>
  </nav>
</main>

<style>
  .lost { max-width: var(--text-col); margin: 0 auto; padding: clamp(72px, 16vh, 160px) var(--gutter) 96px; }
  .kicker { font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0; }
  h1 { font-size: clamp(36px, 6.4vw, 60px); margin: 12px 0 14px; color: var(--ink); }
  .dek { font: 400 clamp(18px, 2vw, 20px)/1.5 var(--sans); color: var(--muted); margin: 0; max-width: 30em; }
  .next { margin: 36px 0 52px; }
  nav h2 { font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; }
  ol { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--grid); }
  li { border-bottom: 1px solid var(--grid); }
  li a {
    display: flex; align-items: center; gap: 14px; min-height: 48px; padding: 0 4px;
    font: 500 16px var(--sans); color: var(--ink); text-decoration: none; border-radius: 6px;
  }
  li a:hover { text-decoration: underline; text-underline-offset: 4px; text-decoration-color: var(--line); }
  li a:focus-visible { outline: none; box-shadow: var(--focus); }
  .n { width: 18px; font-variant-numeric: tabular-nums; color: var(--muted); }
</style>

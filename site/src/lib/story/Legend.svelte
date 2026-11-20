<!--
  The colour key. On wide screens it sits in a corner of the stage. On phones it is a "Key" tab pinned to the bottom of
  the screen that slides up as a sheet, so the chart keeps the whole width and the key is always one tap away.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  // `wide` comes from the page's own layout choice (side by side or pinned on top), not from a separate width cutoff,
  // so the key always matches the layout around it
  let { children, wide = false }: { children?: Snippet; wide?: boolean } = $props();
  let open = $state(false);
  let tabEl = $state<HTMLButtonElement>(), closeEl = $state<HTMLButtonElement>();
  // behaves like a dialog for keyboard users: focus goes into the sheet when it opens and back to the tab when it closes
  function setOpen(v: boolean) {
    open = v;
    queueMicrotask(() => (v ? closeEl : tabEl)?.focus());
  }
  const KEY = [
    { c: 'imdb', t: 'Only on IMDb’s list' },
    { c: 'both', t: 'On both lists' },
    { c: 'lb', t: 'Only on Letterboxd’s list' }
  ];
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && open) setOpen(false); }} />

{#snippet keyList()}
  <ul class="key">
    {#each KEY as k}<li><span class="sw {k.c}"></span>{k.t}</li>{/each}
  </ul>
{/snippet}

{#if wide}
<!-- wide screens: one line in the chart's bottom strip -->
<div class="corner">{@render keyList()}</div>
{:else}
<!-- phones: a tab that opens a bottom sheet -->
<div class="phone">
  <button type="button" class="tab" bind:this={tabEl} aria-expanded={open} aria-controls="key-sheet" onclick={() => setOpen(!open)}>
    <span class="dots" aria-hidden="true"><span class="sw imdb"></span><span class="sw both"></span><span class="sw lb"></span></span>
    Key
  </button>
  {#if open}
    <button type="button" class="scrim" aria-label="Close the key" tabindex="-1" onclick={() => setOpen(false)}></button>
  {/if}
  <div class="sheet" id="key-sheet" class:open role="dialog" aria-label="Colour key and notes" aria-hidden={!open}>
    <div class="bar">
      <strong>Key</strong>
      <button type="button" class="x" bind:this={closeEl} aria-label="Close the key" onclick={() => setOpen(false)} tabindex={open ? 0 : -1}>×</button>
    </div>
    {@render keyList()}
    {#if children}<div class="more">{@render children()}</div>{/if}
  </div>
</div>
{/if}

<style>
  .key { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; font: 500 14px var(--sans); color: var(--ink); }
  .key li { display: flex; align-items: center; gap: 8px; }
  .sw { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; }
  .sw.imdb { background: var(--imdb); box-shadow: inset 0 0 0 1px var(--imdb-edge); }
  .sw.both { background: var(--both); }
  .sw.lb { background: var(--lb); }

  /* wide screens: one line in the stage's bottom band */
  .corner { position: absolute; bottom: 15px; left: var(--clear-left, 24px); right: 300px; z-index: 2; }
  .corner .key { display: flex; flex-wrap: wrap; gap: 6px 18px; }
  .phone { display: block; }

  @media all {
    /* the tab sits in the chart's bottom corner (the camera keeps that strip clear), never over the text */
    /* the pill looks 36px tall, so it has even air above and below in the 49px strip and shares the dots' centre line;
       the ::before keeps the tap area at 44px */
    .tab {
      position: absolute; z-index: 4; left: 8px; bottom: 7px;
      display: inline-flex; align-items: center; gap: 8px; padding: 0 14px; height: 36px; min-width: 44px;
      border-radius: 99px; border: 1px solid var(--line); background: var(--surface); font: 600 14px var(--sans);
      box-shadow: 0 1px 4px rgba(31, 30, 27, 0.08); cursor: pointer;
    }
    .tab::before { content: ''; position: absolute; inset: -5px 0; }
    .dots { display: inline-flex; gap: 3px; }
    .scrim { position: fixed; inset: 0; z-index: 21; background: rgba(31, 30, 27, 0.28); border: 0; padding: 0; cursor: pointer; }
    .sheet {
      position: fixed; z-index: 22; left: 0; right: 0; bottom: 0; padding: 12px 20px calc(24px + env(safe-area-inset-bottom));
      background: var(--surface); border-radius: 16px 16px 0 0; box-shadow: 0 -8px 30px rgba(31, 30, 27, 0.16);
      transform: translateY(105%); transition: transform 0.28s ease; visibility: hidden;
    }
    .sheet.open { transform: none; visibility: visible; }
    .bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font: 600 16px var(--sans); }
    .x { border: 0; background: none; font-size: 24px; line-height: 1; min-width: 44px; min-height: 44px; cursor: pointer; color: var(--muted); }
    .more { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--grid); font: 14px/1.5 var(--sans); color: var(--muted); }
  }
  @media (prefers-reduced-motion: reduce) { .sheet { transition: none; } }
</style>

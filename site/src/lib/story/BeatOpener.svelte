<!--
  The opening title of a beat: a full-width band like a strip of film (sprocket holes along both edges, a little grain),
  near-black. The kicker above the title says "2 of 6".
  The title and the one-line dek follow on the page background.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  interface Props { beat?: number | null; of?: number; label: string; title: string; dek?: string; hero?: boolean; /** no chart follows: no room kept for one to peek in */ compact?: boolean; children?: Snippet; actions?: Snippet; /** more text under the dek (the front page's intro) */ intro?: Snippet }
  let { beat = null, of = 6, label, title, dek = '', hero = false, compact = false, children, actions, intro }: Props = $props();
</script>

<section class="opener" class:hero class:compact>
  <div class="band">
    {#if children}<div class="behind">{@render children()}</div>{/if}
  </div>
  <div class="col text">
    <p class="kicker">{#if beat}<span class="beat">{beat} of {of}</span>{/if} {label}</p>
    <h1>{title}</h1>
    {#if dek}<p class="dek">{dek}</p>{/if}
    {#if intro}<div class="intro">{@render intro()}</div>{/if}
    {#if !compact || actions}
      <div class="cue-row">
        {#if !compact}<p class="cue" aria-hidden="true">Scroll <span>↓</span></p>{/if}
        {#if actions}{@render actions()}{/if}
      </div>
    {/if}
  </div>
</section>

<style>
  /* short enough that the top of the chart peeks into the first screen (below the 52px site header), so readers can
     see there is more below; taller text simply pushes it down */
  .opener {
    --peek: clamp(132px, 20svh, 180px);
    min-height: calc(100svh - 52px - var(--peek)); display: flex; flex-direction: column; justify-content: flex-start;
    gap: 4vh; padding: 0 0 4vh;
  }
  /* wide screens: the chart keeps a taller margin above its first row, so more of it has to show */
  @media (min-width: 900px) { .opener { --peek: clamp(200px, 30svh, 300px); } }
  .opener.compact { min-height: 0; }
  .band {
    /* a strip of black film (near-black, never pure black) */
    --film: #1f1e1b; --hole: #f5f3ee;
    position: relative; height: 52px; overflow: hidden; background: var(--film);
  }
  /* film grain: a fixed noise texture, lifted faintly out of the black */
  .band::before {
    content: ''; position: absolute; inset: 0; pointer-events: none; opacity: 0.08; mix-blend-mode: screen;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0.12 0 0 0 0 0.11 0 0 0 0 0.1 0 0 0 1 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  /* sprocket holes along the top and bottom edges */
  .band::after {
    content: ''; position: absolute; inset: 0; pointer-events: none;
    background:
      repeating-linear-gradient(90deg, var(--hole) 0 14px, transparent 14px 32px) left 18px top 9px / 100% 8px no-repeat,
      repeating-linear-gradient(90deg, var(--hole) 0 14px, transparent 14px 32px) left 18px bottom 9px / 100% 8px no-repeat;
  }
  .behind { position: absolute; inset: 0; }
  /* the front page's band is a dark strip of film holding all 500 dots */
  .hero .band { height: clamp(190px, 34vh, 340px); }
  .text .kicker { font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); display: flex; gap: 10px; align-items: center; margin: 0; }
  .text .beat { color: var(--ink); border: 1px solid var(--line); border-radius: 99px; padding: 2px 9px; letter-spacing: 0.04em; }
  .text h1 { font-size: clamp(36px, 6.4vw, 64px); margin: 12px 0 14px; }
  .hero .text h1 { font-size: clamp(48px, 10vw, 104px); }
  .text .dek { font: 400 clamp(19px, 2vw, 21px)/1.5 var(--sans); color: var(--muted); margin: 0; max-width: 34em; }
  .intro { margin-top: 22px; }
  .cue-row { display: flex; align-items: center; gap: 18px; margin-top: 4vh; }
  .text .cue { font: 500 14px var(--sans); color: var(--muted); margin: 0; }
  .text .cue span { display: inline-block; animation: nudge 1.8s ease-in-out infinite; }
  @keyframes nudge { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(4px); } }
  @media (prefers-reduced-motion: reduce) { .text .cue span { animation: none; } }
</style>

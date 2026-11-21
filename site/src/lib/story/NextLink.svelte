<!--
  The link to the next beat. Deliberately unlike the caption cards: no box, larger display type, a Letterboxd-purple
  kicker, and a hand-drawn scribble under the question. The scribble rests as a faint line and draws itself in full
  colour:
  - with a mouse: on hover;
  - with a keyboard: on focus;
  - on touch screens, where a tap leaves the page before a hover animation could finish: once, as the link scrolls
    into view, so it's already drawn when the reader reaches it. A tap then answers at once (the text dips slightly
    and the arrow nudges) instead of starting an animation that would be cut off.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  let { href, small, q, arrow = '→' }: { href: string; small: string; q: string; arrow?: string } = $props();
  // one gently wavy stroke, drawn at fixed proportions so its length is exactly 1 (pathLength) for the draw-in
  const D = 'M2 10 C 40 4, 80 14, 120 8 S 200 3, 240 9 S 290 13, 318 6';

  let el = $state<HTMLAnchorElement>();
  let seen = $state(false);
  onMount(() => {
    if (!matchMedia('(hover: none)').matches || !('IntersectionObserver' in window)) return;
    // draws once most of the link is on screen (it often sits at the very end of the page, so it can't scroll far
    // past the bottom edge)
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { seen = true; io.disconnect(); } },
      { threshold: 0.75 }
    );
    io.observe(el!);
    return () => io.disconnect();
  });
</script>

<a class="next-link" class:seen {href} bind:this={el}>
  <span class="small">{small}</span>
  <!-- a circular arrow ("start again") turns; a forward arrow nudges forward -->
  <span class="q">{q} <span class="arrow" class:spin={arrow === '↺'} aria-hidden="true">{arrow}</span></span>
  <svg class="scribble" viewBox="0 0 320 16" aria-hidden="true">
    <path class="rest" d={D} />
    <path class="draw" d={D} pathLength="1" />
  </svg>
</a>

<style>
  .next-link { display: block; text-decoration: none; color: var(--ink); padding: 14px 4px 6px; border-radius: 6px; -webkit-tap-highlight-color: transparent; }
  .small { display: block; font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--lb-ink); margin-bottom: 6px; }
  .q { display: block; font: 560 clamp(24px, 2.4vw, 30px)/1.2 var(--display); letter-spacing: -0.01em; transform-origin: left center; transition: transform 0.12s ease; }
  .arrow { display: inline-block; transition: transform 0.25s ease; }
  .arrow.spin { transition: transform 0.6s cubic-bezier(0.65, 0, 0.35, 1); transform-origin: 50% 55%; }
  .scribble { display: block; width: min(100%, 380px); height: auto; margin-top: 6px; overflow: visible; }
  .scribble path { fill: none; stroke-width: 3; stroke-linecap: round; }
  .rest { stroke: var(--line); }
  /* at rest the dash pattern leaves a round cap showing as a dot at the line's end, so the purple line is hidden
     until it draws, and hides again only once it has fully drawn back */
  .draw {
    stroke: var(--lb); stroke-dasharray: 1; stroke-dashoffset: 1; opacity: 0;
    transition: stroke-dashoffset 0.7s cubic-bezier(0.65, 0, 0.35, 1), opacity 0s linear 0.7s;
  }
  /* drawn: keyboard focus, or (touch screens) scrolled into view */
  .next-link:focus-visible .draw { stroke-dashoffset: 0; opacity: 1; transition-delay: 0s, 0s; }
  .next-link.seen .draw { stroke-dashoffset: 0; opacity: 1; transition: stroke-dashoffset 0.9s cubic-bezier(0.65, 0, 0.35, 1) 0.15s, opacity 0s linear 0.15s; }
  .next-link:focus-visible .arrow { transform: translateX(6px); }
  .next-link:focus-visible .arrow.spin { transform: rotate(-360deg); }

  /* mouse and trackpad only, so a tap never sets off a half-played hover */
  @media (hover: hover) and (pointer: fine) {
    .next-link:hover .draw { stroke-dashoffset: 0; opacity: 1; transition-delay: 0s, 0s; }
    .next-link:hover .arrow { transform: translateX(6px); }
    .next-link:hover .arrow.spin { transform: rotate(-360deg); }
  }

  /* touch: instant answer while the finger is down */
  @media (hover: none) {
    .next-link:active .q { transform: scale(0.98); }
    .next-link:active .arrow { transform: translateX(6px); transition-duration: 0.12s; }
    .next-link:active .arrow.spin { transform: rotate(-90deg); }
    .next-link:active .draw { stroke-dashoffset: 0; opacity: 1; transition: none; }
  }

  @media (prefers-reduced-motion: reduce) {
    .draw, .next-link.seen .draw, .arrow, .q { transition: none; }
    .next-link:active .q { transform: none; }
  }
</style>

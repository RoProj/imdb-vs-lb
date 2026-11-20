<!--
  The link to the next beat. Deliberately unlike the caption cards: no box, larger display type, a Letterboxd-purple
  kicker, and a hand-drawn scribble under the question. The scribble rests as a faint line and draws itself in full
  colour on hover or keyboard focus.
-->
<script lang="ts">
  let { href, small, q, arrow = '→' }: { href: string; small: string; q: string; arrow?: string } = $props();
  // one gently wavy stroke, drawn at fixed proportions so its length is exactly 1 (pathLength) for the draw-in
  const D = 'M2 10 C 40 4, 80 14, 120 8 S 200 3, 240 9 S 290 13, 318 6';
</script>

<a class="next-link" {href}>
  <span class="small">{small}</span>
  <!-- a circular arrow ("start again") turns on hover; a forward arrow nudges forward -->
  <span class="q">{q} <span class="arrow" class:spin={arrow === '↺'} aria-hidden="true">{arrow}</span></span>
  <svg class="scribble" viewBox="0 0 320 16" aria-hidden="true">
    <path class="rest" d={D} />
    <path class="draw" d={D} pathLength="1" />
  </svg>
</a>

<style>
  .next-link { display: block; text-decoration: none; color: var(--ink); padding: 14px 4px 6px; border-radius: 6px; }
  .small { display: block; font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; color: var(--lb-ink); margin-bottom: 6px; }
  .q { display: block; font: 560 clamp(24px, 2.4vw, 30px)/1.2 var(--display); letter-spacing: -0.01em; }
  .arrow { display: inline-block; transition: transform 0.25s ease; }
  .arrow.spin { transition: transform 0.6s cubic-bezier(0.65, 0, 0.35, 1); transform-origin: 50% 55%; }
  .scribble { display: block; width: min(100%, 380px); height: auto; margin-top: 6px; overflow: visible; }
  .scribble path { fill: none; stroke-width: 3; stroke-linecap: round; }
  .rest { stroke: var(--line); }
  .draw { stroke: var(--lb); stroke-dasharray: 1; stroke-dashoffset: 1; transition: stroke-dashoffset 0.7s cubic-bezier(0.65, 0, 0.35, 1); }
  .next-link:hover .draw, .next-link:focus-visible .draw { stroke-dashoffset: 0; }
  .next-link:hover .arrow, .next-link:focus-visible .arrow { transform: translateX(6px); }
  .next-link:hover .arrow.spin, .next-link:focus-visible .arrow.spin { transform: rotate(-360deg); }
  @media (prefers-reduced-motion: reduce) { .draw, .arrow { transition: none; } }
</style>

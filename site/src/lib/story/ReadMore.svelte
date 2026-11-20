<!--
  A block of text that shows its first two lines, then opens to full length with "Read more".
  The height animates between the two measured sizes (never a jump), the last visible line fades out while closed,
  and the hidden part is inert (no focus, no screen-reader reading of half-hidden text) until it opens.
  Closing from far down scrolls back up with it, so the reader isn't left below a page that just shrank.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  interface Props { lines?: number; id: string; teaser: Snippet; children: Snippet }
  let { lines = 2, id, teaser, children }: Props = $props();

  let open = $state(false);
  let shut = $state(true);              // true once fully closed: hides the rest from keyboard and screen readers
  let box = $state<HTMLDivElement>();
  let first = $state<HTMLDivElement>();
  let closedH = 0;
  let reduce = false;
  let raf = 0;
  const setH = (h: string) => { if (box) box.style.height = h; };

  function closedHeight() {
    if (!first) return 0;
    const lh = parseFloat(getComputedStyle(first.firstElementChild ?? first).lineHeight) || 26;
    return Math.round(lh * lines);
  }

  onMount(() => {
    reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    closedH = closedHeight();
    setH(`${closedH}px`);
    const ro = new ResizeObserver(() => {
      closedH = closedHeight();
      if (!open && !raf) setH(`${closedH}px`);
    });
    ro.observe(first!);
    return () => { ro.disconnect(); cancelAnimationFrame(raf); };
  });

  // one gentle in-and-out curve: no sudden lurch at the start, no long crawl at the end
  const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  // longer moves take a little longer, so a tall block never snaps
  const dur = (d: number) => Math.round(Math.min(720, Math.max(380, 300 + d * 0.22)));

  // Height and page scroll run on ONE timeline, so they can't fight: while the text closes, the page scrolls by just
  // enough to land the start of the text near the top of the screen, and the "Read less" button glides there with it.
  function animate(from: number, to: number, scrollTo: number | null, finish: () => void) {
    cancelAnimationFrame(raf);
    const s0 = scrollY, ms = dur(Math.abs(to - from)), t0 = performance.now();
    let userScrolled = false;
    const stop = () => (userScrolled = true);                    // the reader takes over: stop steering the scroll
    addEventListener('wheel', stop, { passive: true, once: true });
    addEventListener('touchstart', stop, { passive: true, once: true });
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / ms), e = ease(t);
      setH(`${from + (to - from) * e}px`);
      if (scrollTo !== null && !userScrolled) window.scrollTo({ top: s0 + (scrollTo - s0) * e, behavior: 'instant' as ScrollBehavior });
      if (t < 1) raf = requestAnimationFrame(step);
      else { raf = 0; removeEventListener('wheel', stop); removeEventListener('touchstart', stop); finish(); }
    };
    raf = requestAnimationFrame(step);
  }

  function toggle() {
    if (!box) return;
    const now = box.getBoundingClientRect().height;
    if (!open) {
      shut = false; open = true;
      const full = box.scrollHeight;
      if (reduce) return setH('auto');
      animate(now, full, null, () => setH('auto'));           // auto afterwards: follows font loads and rotation
    } else {
      open = false;
      // where the page should end up: the start of the text a little below the top, if it's currently above that
      const top = box.getBoundingClientRect().top;
      const target = top < 72 ? Math.max(0, scrollY + top - 96) : null;
      if (reduce) {
        setH(`${closedH}px`); shut = true;
        if (target !== null) window.scrollTo({ top: target, behavior: 'instant' as ScrollBehavior });
        return;
      }
      animate(now, closedH, target, () => (shut = true));
    }
  }
</script>

<div class="readmore" class:open>
  <div class="box" bind:this={box} {id}>
    <div class="first" bind:this={first}>{@render teaser()}</div>
    <div class="rest" inert={shut}>{@render children()}</div>
  </div>
  <button type="button" class="toggle" aria-expanded={open} aria-controls={id} onclick={toggle}>
    <span>{open ? 'Read less' : 'Read more'}</span>
    <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
  </button>
</div>

<style>
  .readmore { position: relative; max-width: 34em; }
  .box { position: relative; overflow: hidden; }
  /* the last visible line fades into the page while closed */
  .box::after {
    content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 1.6em; pointer-events: none;
    background: linear-gradient(to bottom, transparent, var(--bg));
    opacity: 1; transition: opacity 260ms ease 280ms;   /* comes back as the box lands */
  }
  .open .box::after { opacity: 0; transition-delay: 0ms; }
  /* closing: the extra text fades first, so the box folds up over a calm, near-empty area */
  .rest { opacity: 0; transition: opacity 220ms ease-out; }
  .open .rest { opacity: 1; transition: opacity 420ms ease 120ms; }

  .toggle {
    display: inline-flex; align-items: center; gap: 6px; min-height: 44px; margin-top: 2px; padding: 0;
    border: 0; background: none; cursor: pointer; color: var(--ink); font: 600 14px var(--sans);
  }
  .toggle span { text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 4px; text-decoration-thickness: 1px; transition: text-decoration-color 160ms; }
  .toggle:hover span { text-decoration-color: var(--ink); }
  .toggle svg { transition: transform 420ms cubic-bezier(0.22, 0.7, 0.18, 1); }
  .open .toggle svg { transform: rotate(180deg); }
  .toggle:focus-visible { outline: none; box-shadow: var(--focus); border-radius: 6px; }

  @media (prefers-reduced-motion: reduce) {
    .box::after, .rest, .toggle svg { transition: none; }
  }
</style>

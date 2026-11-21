<!--
  One beat of the guided story: the scroll machinery shared by every beat.
  - Ordinary page scrolling drives it, continuously: scroll position becomes `progress` (2.4 = 40% of the way from
    step 2 to step 3) and the stage blends camera, colours and labels between the two. Each step holds still while its
    card is read and only blends in the gap before the next card: one motion at a time. Nothing hijacks the scroll.
  - Each step has its own link (?step=<id>); a shared link opens on its step.
  - Phones: the chart is pinned to the top 60% of the screen and the cards scroll up underneath it, so text never covers
    the chart and the chart never covers text. Wide screens (and phones held sideways): cards left, chart pinned right.
  - Sizes come from window.innerHeight in px (not vh units, which phone toolbars change while scrolling).
  The page supplies the layout, the steps (view + colouring), the card for each step, and the key's note.
-->
<script lang="ts">
  import { onMount, tick, type Snippet } from 'svelte';
  import { replaceState } from '$app/navigation';
  import StoryStage, { type StageStep } from './StoryStage.svelte';
  import Legend from './Legend.svelte';
  import FilmTip from '$lib/engine/FilmTip.svelte';
  import { parseKey, type Film, type Layout, type Numbers } from '$lib/data';

  interface Props {
    layout: Layout;
    steps: StageStep[];
    ids: string[];
    numbers: Numbers;
    films: Map<string, Film>;
    /** what the chart shows, for screen readers */
    summary: string;
    card: Snippet<[number]>;
    keyNote?: Snippet;
    /** the link to the next beat, shown right under the last card so readers don't miss it */
    next?: Snippet;
    /** how many steps are open; the rest stay hidden until the page opens them (e.g. after the reader answers a question) */
    visible?: number;
    active?: number;
    /** film cards show Letterboxd's whole Top 500 (the disagreements page); otherwise only its Top 250 counts */
    lbTop500?: boolean;
  }
  let { layout, steps, ids, numbers, films, summary, card, keyNote, next, visible, active = $bindable(0), lbTop500 = false }: Props = $props();
  const shownIds = $derived(ids.slice(0, visible ?? ids.length));

  // The page ends where the last link to the next beat sits in the middle of the screen (wide screens), or where the
  // last caption sits just under the pinned chart (phones), so the closing card is never cut off. The spacer after
  // the last step is measured to make that happen rather than guessed.
  let stepsEl = $state<HTMLElement>();
  let tailH = $state(0);
  function fitTail() {
    const last = stepEls[shownIds.length - 1];
    const cardEl = last?.querySelector('.card'), nextEl = last?.querySelector('.next');
    if (!last || !cardEl || !nextEl || shownIds.length !== ids.length) { tailH = 0; return; }
    const end = last.getBoundingClientRect().bottom; // where the content ends, without the spacer
    const card = cardEl.getBoundingClientRect(), nxt = nextEl.getBoundingClientRect();
    // at the very bottom of the page, the document's end is at the bottom of the screen (vh)
    const want = wide
      ? (nxt.top + nxt.bottom) / 2 + vh / 2 // link centred on the screen
      : card.top - (stageH + 12) + vh; // caption just under the chart
    tailH = Math.max(0, Math.round(want - end));
  }
  $effect(() => {
    void shownIds; void wide; void vh; void stageH;
    if (!stepsEl) return;
    requestAnimationFrame(fitTail);
    const ro = new ResizeObserver(() => fitTail());
    ro.observe(stepsEl);
    return () => ro.disconnect();
  });


  let vh = $state(800), vw = $state(1200);
  // side by side on wide screens and on phones held sideways (where 60% of a short screen would be too little chart)
  const wide = $derived(vw >= 900 || (vw > vh && vw >= 640));
  const stageH = $derived(wide ? vh : Math.round(vh * 0.6));
  // wide screens: the chart fills the screen and the cards float in a column on the left; the camera keeps the dots
  // to the right of that column (Both Sides' full-width layout)
  const cardPad = $derived(Math.max(16, Math.round(vw * 0.04)));
  const cardW = $derived(Math.min(440, Math.round(vw * 0.34)));
  const clearLeft = $derived(cardPad + cardW + 40);
  let stepEls: HTMLElement[] = $state([]);
  let progress = $state(0);
  // The first frame sits near the top of the chart, so it is what peeks into the first screen under the opener; it
  // holds still until the first caption moves it on.
  const stageSteps = $derived(steps.map((s, i) => (i === 0 && !s.view.noPeek ? { ...s, view: { ...s.view, peekTop: 72 } } : s)));
  let userScrolled = false;
  // each step holds still for at least this share of the scroll between two cards, then blends into the next
  const HOLD = 0.45;

  function measure() {
    // Re-measure on width changes (rotation, window resize) and on big height changes (split screen, a resized window),
    // but not when a phone's toolbar slides in or out (under about 150 px), which would make the chart jump mid-scroll.
    if (window.innerWidth !== vw || !vh || Math.abs(window.innerHeight - vh) > 150) { vw = window.innerWidth; vh = window.innerHeight; }
  }
  // Every chart change is tied to its caption card, not to the step's box around it. A change starts once the
  // incoming card is clearly on screen and finishes exactly as that card reaches its reading spot: centred a little
  // above the middle of the screen on wide screens, just under the pinned chart on phones. Between those, the chart
  // holds still while the reader reads.
  let lit = $state(0); // the caption drawn at full strength (see readProgress)
  const cardOf = (el: HTMLElement | undefined) => (el?.querySelector('.card') as HTMLElement | null) ?? el;
  /** where a card's top sits when its step is fully in place (screen y) */
  const restTop = (h: number) => (wide ? vh * 0.45 - h / 2 : stageH + 12);
  /** how far before its resting place the card's change begins */
  const runIn = (span: number) => Math.min(wide ? vh * 0.35 : (vh - stageH) * 0.5, span * (1 - HOLD));

  /** scroll so step i's caption sits where it's read, with the chart showing that step */
  function goTo(i: number) {
    const c = cardOf(stepEls[i])?.getBoundingClientRect();
    if (!c) return;
    userScrolled = true;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: c.top + scrollY - restTop(c.height) + 1, behavior: reduce ? 'instant' as ScrollBehavior : 'smooth' });
  }

  function readProgress() {
    if (!stepEls.length || !stepEls[0]) return;
    // only the steps that are open count (a held-back step's element may linger in the array)
    const cards = stepEls.slice(0, shownIds.length).map((el) => cardOf(el)?.getBoundingClientRect());
    let p = 0;
    for (let j = 1; j < cards.length; j++) {
      const c = cards[j], prev = cards[j - 1];
      if (!c || !prev) break;
      const end = restTop(c.height), d = runIn(c.top - prev.top);
      const t = d > 0 ? (end + d - c.top) / d : c.top <= end ? 1 : 0;
      if (t <= 0) break;
      p = j - 1 + Math.min(1, t);
    }
    progress = p;
    // the caption shown at full strength: of the captions on screen, the one nearest the reading line. A caption only
    // dims when another one is on screen and closer, so a lone caption is never greyed out.
    let best = active, bestD = Infinity;
    cards.forEach((c, j) => {
      if (!c || c.bottom <= 0 || c.top >= vh) return;
      const d = Math.abs(c.top + c.height / 2 - (wide ? vh * 0.45 : stageH + 12 + c.height / 2));
      if (d < bestD) { bestD = d; best = j; }
    });
    lit = bestD === Infinity ? Math.round(p) : best;
    if (import.meta.env.DEV) Object.assign(window as any, { __storyProgress: p, __readProgress: readProgress }); // dev only: scroll-sync checks
    const now = Math.round(p);
    if (now !== active) {
      active = now;
      if (userScrolled) {
        const url = new URL(location.href);
        url.searchParams.set('step', ids[now]);
        replaceState(url, {});
      }
    }
  }

  let ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      // a big height change the browser didn't announce with a resize event (seen in some emulators): catch it here
      if (Math.abs(window.innerHeight - vh) > 150) measure();
      readProgress();
      readLift();
    });
  }

  // Phones: the page ends with END_SPACE of room under the last link. Over that last stretch the pinned chart slides
  // up with the page, so the closing caption stays fully visible right under it.
  const END_SPACE = 48;
  let lift = $state(0);
  function readLift() {
    if (wide || !next || shownIds.length !== ids.length) { lift = 0; return; }
    const left = document.documentElement.scrollHeight - (scrollY + window.innerHeight); // px still to scroll
    lift = Math.round(Math.max(0, Math.min(END_SPACE, END_SPACE - left)));
  }

  // On phones the pinned chart covers the top 60% of the screen. When the browser scrolls a focused button or link into
  // view (keyboard users, screen readers), keep it below the chart, never hidden under it (WCAG 2.2, focus not obscured).
  $effect(() => {
    const el = document.documentElement;
    el.style.scrollPaddingTop = wide ? '' : `${stageH + 12}px`;
    return () => { el.style.scrollPaddingTop = ''; };
  });

  onMount(() => {
    vw = window.innerWidth; vh = window.innerHeight;
    const markUser = () => (userScrolled = true);
    window.addEventListener('wheel', markUser, { passive: true, once: true });
    window.addEventListener('touchmove', markUser, { passive: true, once: true });
    window.addEventListener('keydown', markUser, { once: true });
    (async () => {
      await tick();
      const j = ids.indexOf(new URL(location.href).searchParams.get('step') ?? '');
      // a link to a step that isn't open yet (held back until the reader answers) lands on the first step
      if (j >= shownIds.length) {
        const url = new URL(location.href);
        url.searchParams.delete('step');
        replaceState(url, {});
      }
      if (j > 0 && j < shownIds.length && stepEls[j]) {
        const c = cardOf(stepEls[j])!.getBoundingClientRect();
        window.scrollTo({ top: c.top + scrollY - restTop(c.height) + 1, behavior: 'instant' as ScrollBehavior });
      }
      readProgress();
    })();
  });
</script>

<svelte:window onscroll={onScroll} onresize={() => { measure(); onScroll(); }} />

<div class="scrolly" class:is-wide={wide} style="--vh:{vh}px; --stage:{stageH}px; --card-w:{cardW}px; --card-pad:{cardPad}px; --clear-left:{clearLeft}px">
  <div class="stage-wrap" style:transform={lift ? `translateY(${-lift}px)` : null}>
    <p class="sr-only">{summary}</p>
    <StoryStage
      {layout}
      steps={stageSteps}
      {progress}
      {numbers}
      inset={wide ? { top: 128, right: 32, bottom: 52, left: clearLeft } : { top: 34, right: 6, bottom: 54, left: 6 }}
      edges={wide}
    >
      {#snippet tip(key)}
        {@const f = films.get(parseKey(key).id ?? '')}
        {#if f}<FilmTip film={f} lbScope={lbTop500 ? 500 : 250} />{/if}
      {/snippet}
    </StoryStage>
    <Legend {wide}>{#if keyNote}{@render keyNote()}{/if}</Legend>
    <!-- the step dots, on the bottom strip (the address bar always holds a link to the current step) -->
    <div class="tools">
    <!-- one dot per step: shows where the reader is, and jumps to a step when pressed -->
    <nav aria-label="Steps on this page">
      <ol class="progress">
        {#each ids as _, i}
          <li>
            <button
              type="button" class:on={i === active} class:done={i < active}
              aria-current={i === active ? 'step' : undefined}
              aria-label={i < shownIds.length ? `Step ${i + 1} of ${ids.length}` : `Step ${i + 1} of ${ids.length}, opens after you answer`}
              disabled={i >= shownIds.length}
              onclick={() => goTo(i)}
            ><span></span></button>
          </li>
        {/each}
      </ol>
    </nav>
    </div>
  </div>

  <div class="steps" bind:this={stepsEl}>
    {#each shownIds as id, i}
      <section class="step" id="step-{id}" bind:this={stepEls[i]} class:active={lit === i} class:last={!!next && i === ids.length - 1}>
        <div class="card">{@render card(i)}</div>
        {#if next && i === ids.length - 1}<div class="next">{@render next()}</div>{/if}
      </section>
    {/each}
    {#if shownIds.length === ids.length}<div class="tail" aria-hidden="true" style:height="{tailH}px"></div>{/if}
  </div>
</div>
<!-- phones: breathing room under the last link. It sits outside the sticky area, so the chart and caption scroll
     up together and the caption stays fully visible -->
{#if !wide && next && shownIds.length === ids.length}<div class="end-space" aria-hidden="true"></div>{/if}

<style>
  /* ---------------- phones first */
  .scrolly { position: relative; }
  .end-space { height: 48px; } /* matches END_SPACE */
  .stage-wrap {
    position: sticky; top: 0; height: var(--stage); z-index: 5; background: var(--bg);
    border-bottom: 1px solid var(--grid);
  }
  /* a soft edge where cards slide under the chart */
  .stage-wrap::after {
    content: ''; position: absolute; left: 0; right: 0; bottom: -18px; height: 18px; pointer-events: none;
    background: linear-gradient(var(--bg), color-mix(in srgb, var(--bg) 0%, transparent));
  }
  .steps { position: relative; z-index: 1; padding: 0 var(--gutter); }
  /* phones: cards follow each other closely, so the reading area below the chart is never mostly empty */
  .step { min-height: calc((var(--vh) - var(--stage)) * 0.62); display: flex; flex-direction: column; align-items: stretch; justify-content: flex-start; gap: 14px; padding-top: 14px; }
  .next { width: 100%; max-width: 440px; margin: 0 auto; }
  .step:first-child { padding-top: 22px; }
  /* just enough room for the last card to reach the trigger line, so the page carries on without an empty stretch */
  .step.last { min-height: 0; }

  .card {
    width: 100%; max-width: 440px; margin: 0 auto; background: var(--surface); border: 1.5px dotted var(--muted); border-radius: 10px;
    padding: 16px 18px; font: 16px/1.6 var(--sans); color: var(--ink); transition: opacity 0.3s;
  }
  .card :global(p) { margin: 0 0 10px; }
  .card :global(p:last-child) { margin-bottom: 0; }
  .card :global(.lead) { font: 650 19px/1.3 var(--sans); letter-spacing: -0.01em; margin: 0 0 8px; }
  .card :global(.aside) { color: var(--muted); font-size: 14px; }
  .card :global(.mini) { width: 100%; border-collapse: collapse; font: 14px var(--sans); margin-top: 6px; font-variant-numeric: tabular-nums; }
  .card :global(.mini th), .card :global(.mini td) { padding: 4px 0; border-bottom: 1px solid var(--grid); text-align: right; }
  .card :global(.mini th[scope='row']), .card :global(.mini thead th:first-child) { text-align: left; font-weight: 500; }
  .card :global(.mini thead th) { font-size: 12px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
  .card :global(.mini thead .imdb), .card :global(.mini thead .lb) { padding: 0; }
  .card :global(.mini thead .imdb span), .card :global(.mini thead .lb span) { display: inline-block; border-radius: 4px; padding: 1px 7px; }
  .card :global(.mini thead .imdb span) { background: var(--imdb-tag); color: var(--imdb-tag-ink); }
  .card :global(.mini thead .lb span) { background: var(--lb-tag); color: var(--lb-tag-ink); }

  /* the bottom strip is (inset.bottom - 4) px tall; this row is 44 px tall and sits on its centre line */
  .tools { position: absolute; z-index: 3; right: 14px; bottom: 3px; height: 44px; display: flex; align-items: center; gap: 10px; }
  .is-wide .tools { right: 32px; bottom: 2px; }
  .progress { display: flex; align-items: center; gap: 0; list-style: none; margin: 0 -9px 0 0; padding: 0; }
  /* each dot sits in a 24px button (WCAG 2.2 target size), so the row looks as it did but is easy to hit */
  .progress button {
    width: 24px; height: 24px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 50%;
    background: none; cursor: pointer; pointer-events: auto;
  }
  .progress button span { width: 6px; height: 6px; border-radius: 50%; background: var(--faint); transition: background 0.3s, transform 0.3s; }
  .progress button.done span { background: var(--muted); }
  .progress button.on span { background: var(--ink); transform: scale(1.35); }
  .progress button:not(:disabled):hover span { background: var(--ink); transform: scale(1.5); }
  .progress button:disabled { cursor: default; }
  .progress button:disabled span { opacity: 0.5; }
  .progress button:focus-visible { outline: none; box-shadow: var(--focus); }

  /* ---------------- wide screens: the chart fills the screen, cards float over its left side */
  .is-wide .stage-wrap { height: var(--vh); border-bottom: 0; }
  .is-wide .stage-wrap::after { display: none; }
  /* the cards' column lies over the chart; only the cards themselves catch the pointer, so the dots stay hoverable */
  .is-wide .steps { z-index: 6; margin-top: calc(var(--vh) * -1); width: calc(var(--card-w) + var(--card-pad)); padding: 0 0 0 var(--card-pad); pointer-events: none; }
  .is-wide .step { min-height: calc(var(--vh) * 0.85); justify-content: center; padding-top: 0; }
  .is-wide .next { max-width: none; margin: 0; pointer-events: auto; }
  /* the first caption sits where every caption is read (45% down the screen) once the chart settles, not near the top */
  .is-wide .step:first-child { min-height: var(--vh); justify-content: center; padding-top: 0; padding-bottom: calc(var(--vh) * 0.1); }
  .is-wide .step.last { min-height: 0; padding-top: 6vh; }
  .is-wide .card { margin: 0; max-width: none; pointer-events: auto; padding: 22px 24px; font-size: 18px; box-shadow: 0 10px 34px rgba(31, 30, 27, 0.08); }
  .is-wide .card :global(.lead) { font-size: 21px; }
  .is-wide .step:not(.active) .card { opacity: 0.35; }


  @media (prefers-reduced-motion: reduce) { .card, .progress button span { transition: none; } }
</style>

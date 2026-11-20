<!--
  The sticky stage of a scrollytelling beat: one canvas, one layout, a camera, and a list of steps.
  Scroll drives it continuously ("scrubbing"): the page passes `progress`, a number like 2.4 meaning
  "40% of the way from step 2 to step 3". Camera, colours and labels are all blended between the two steps,
  so the chart moves with the reader's finger instead of waiting for a threshold and then playing a fixed animation.
  A light damping on top smooths trackpad and touch jitter. One motion at a time: the page holds each step while its
  card is read and only blends during the gap between cards.
  - The camera belongs to the story: no reader zoom or pan here. Hover or tap a dot still opens its card.
  - Dots scale with the camera (a little less than the spacing when zooming in, so they never collide); text stays a fixed size.
  - Reduced motion: no blending; the stage cuts to whichever step is current.
-->
<script lang="ts" module>
  export interface View { rows?: string[]; keys?: string[]; pad?: number; maxK?: number; /** pin the framed area to the top of the stage */ alignTop?: boolean;
    /** the framed subject sits this many px below the top strip instead of in the middle, so it shows while only the
        top of the chart has scrolled into view (a page's first frame, peeking in under the opener) */
    peekTop?: number;
    /** first step only: keep this exact framing (no peek offset), e.g. when the next step uses the same view */
    noPeek?: boolean }
  export interface StageNote { key: string; title: string; /** a shorter title for phone-width charts */ titleNarrow?: string; text?: string; dx: number; dy: number }
  export interface StageStep {
    view: View;
    style: (key: string) => { fill: string; stroke?: string; alpha?: number };
    /** rows whose labels stay at full strength; null = all */
    focusRows?: string[] | null;
    /** 0 hides the rows' own labels (the IMDb / Letterboxd header and the centre line always show) */
    decoAlpha?: number;
    notes?: StageNote[];
    /** hide the count labels (e.g. while the reader is asked to guess) */
    hideCounts?: boolean;
    /** the step's two key numbers, shown large under each side's name on wide screens: [IMDb, Letterboxd] */
    stat?: [string, string];
    /** false for steps whose chart isn't two-sided (e.g. three groups): the side names fade out */
    sides?: boolean;
    /** a different arrangement of the same dots for this step (same keys, same order); dots move between steps */
    layout?: Layout;
    /** style of the line joining a film's two dots (same id on both lists); null = no line */
    link?: (id: string) => { color: string; alpha: number; width: number } | null;
  }
</script>

<script lang="ts">
  import { onDestroy, onMount, type Snippet } from 'svelte';
  import { quadtree, type Quadtree } from 'd3-quadtree';
  import { fill, parseKey, token, prefersReducedMotion, type Layout, type Numbers, type Variant } from '$lib/data';

  interface Props {
    layout: Layout;
    steps: StageStep[];
    progress: number;
    numbers: Numbers;
    inset?: { top: number; right: number; bottom: number; left: number };
    narrowBelow?: number;
    tip?: Snippet<[string]>;
    selected?: string | null;
    /** wide screens: name the sides at the edges of the chart, with each step's key numbers, instead of a small centred header */
    edges?: boolean;
  }
  let {
    layout, steps, progress, numbers, inset = { top: 16, right: 16, bottom: 16, left: 16 }, narrowBelow = 560, tip,
    selected = $bindable(null), edges = false
  }: Props = $props();
  // the edge labels' state, updated each frame as the steps blend
  let sidesOp = $state(1);
  let stat = $state<[string, string] | null>(null);
  let statOp = $state(1);

  type Row = { t: string; key: string; y0: number; y1: number };
  let canvas: HTMLCanvasElement;
  let cw = $state(0), ch = $state(0);
  type V = Variant & { rows?: Row[] };
  const narrowNow = $derived(!!cw && cw < narrowBelow);
  const variant: V = $derived(narrowNow ? layout.narrow : layout.wide);
  const variantOf = (s: StageStep): V => { const l = s.layout ?? layout; return narrowNow ? l.narrow : l.wide; };
  // positions this frame (blended between two layouts when a step changes arrangement)
  let xyNow: ArrayLike<number> = [];
  let rNow = 1;
  let vA: V, vB: V;

  let ctx: CanvasRenderingContext2D | null = null;
  let dpr = 1;
  let col: Record<string, string> = {};
  let raf = 0, lastT = 0;
  const invalidate = () => { if (!raf && typeof requestAnimationFrame !== 'undefined') raf = requestAnimationFrame(draw); };

  // ---------------------------------------------------------------- per-step precomputation
  type Cam = { x: number; y: number; k: number };
  type Paint = { rgb: Float32Array; alpha: Float32Array; stroke: (string | undefined)[] };
  let cams: Cam[] = [];
  let paints: Paint[] = [];

  function hexRgb(c: string): [number, number, number] {
    const m = c.trim().match(/^#?([0-9a-f]{6})$/i);
    if (!m) return [128, 128, 128];
    const v = parseInt(m[1], 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }

  function camFor(v: View, va: V): Cam {
    const xy = va.xy, ks = layout.keys, cx = va.w / 2;
    let x0 = 0, x1 = va.w, y0 = 0, y1 = va.h;
    if (v.rows?.length && va.rows) {
      const bands = va.rows.filter((r) => v.rows!.includes(r.t));
      y0 = Math.min(...bands.map((b) => b.y0));
      y1 = Math.max(...bands.map((b) => b.y1));
      // symmetric about the centre line, wide enough for the widest block and its count label
      let half = 40;
      for (let i = 0; i < ks.length; i++) {
        const y = xy[2 * i + 1];
        if (y > y0 && y < y1) half = Math.max(half, Math.abs(xy[2 * i] - cx) + va.r + 42);
      }
      x0 = cx - half; x1 = cx + half;
    } else if (v.keys?.length) {
      const idx = v.keys.map((k) => ks.indexOf(k)).filter((i) => i >= 0);
      x0 = Math.min(...idx.map((i) => xy[2 * i])); x1 = Math.max(...idx.map((i) => xy[2 * i]));
      y0 = Math.min(...idx.map((i) => xy[2 * i + 1])); y1 = Math.max(...idx.map((i) => xy[2 * i + 1]));
    }
    const p = v.pad ?? 8;
    x0 -= p; x1 += p; y0 -= p; y1 += p;
    const w = cw - inset.left - inset.right, h = ch - inset.top - inset.bottom;
    const k = Math.min(v.maxK ?? 2.4, Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.96);
    // pinned to the top: the framed area starts at the top of the stage and what follows it fills the rest
    const framed = !!(v.rows?.length || v.keys?.length);
    // (capped so a tall frame, e.g. two dots far apart, still starts at the top strip rather than above it)
    const cy = v.peekTop !== undefined && framed ? Math.min((y0 + y1) / 2 + (h / 2 - v.peekTop) / k, y0 + h / k / 2)
      : v.alignTop || v.peekTop !== undefined ? y0 + h / k / 2 : (y0 + y1) / 2;
    return { x: (x0 + x1) / 2, y: cy, k };
  }

  $effect(() => {
    const ss = steps;
    void inset; void narrowNow;
    if (!cw || !ch) return;
    cams = ss.map((s) => camFor(s.view, variantOf(s)));
    invalidate();
  });

  $effect(() => {
    const ks = layout.keys, ss = steps;
    paints = ss.map((s) => {
      const rgb = new Float32Array(ks.length * 3), alpha = new Float32Array(ks.length), stroke: (string | undefined)[] = [];
      ks.forEach((key, i) => {
        const d = s.style(key);
        const [r, g, b] = hexRgb(d.fill);
        rgb[3 * i] = r; rgb[3 * i + 1] = g; rgb[3 * i + 2] = b;
        alpha[i] = d.alpha ?? 1;
        stroke.push(d.stroke);
      });
      return { rgb, alpha, stroke };
    });
    invalidate();
  });

  // lines join a film's two dots: id:i and id:l
  const pairs = $derived.by(() => {
    const at = new Map<string, number>();
    layout.keys.forEach((k, i) => { if (k.endsWith(':i')) at.set(k.slice(0, -2), i); });
    const out: { id: string; a: number; b: number }[] = [];
    layout.keys.forEach((k, i) => { if (k.endsWith(':l')) { const id = k.slice(0, -2); const a = at.get(id); if (a !== undefined) out.push({ id, a, b: i }); } });
    return out;
  });
  type LinkPaint = { rgb: Float32Array; alpha: Float32Array; width: Float32Array };
  let linkPaints: LinkPaint[] = [];
  $effect(() => {
    const ps = pairs, ss = steps;
    linkPaints = ss.map((s) => {
      const rgb = new Float32Array(ps.length * 3), alpha = new Float32Array(ps.length), width = new Float32Array(ps.length);
      ps.forEach((p, j) => {
        const st = s.link?.(p.id);
        if (!st) return;
        const [r, g, b] = hexRgb(st.color);
        rgb[3 * j] = r; rgb[3 * j + 1] = g; rgb[3 * j + 2] = b;
        alpha[j] = st.alpha; width[j] = st.width;
      });
      return { rgb, alpha, width };
    });
    invalidate();
  });

  // ---------------------------------------------------------------- progress, damped
  // `shownP` chases `progress` with a short time constant: smooth on a trackpad, still tightly tied to the finger.
  let shownP = -1;
  const TAU = 60; // ms: enough to smooth a trackpad's steps without visibly trailing the page
  $effect(() => { void progress; invalidate(); });

  $effect(() => {
    if (!canvas || !cw || !ch) return;
    dpr = Math.min(2.5, window.devicePixelRatio || 1);
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
    invalidate();
  });

  // reduced motion only: fade the chart out, swap to the step the reader is now on, fade back in
  let rmFade = 0;
  const FADE_OUT = 140, FADE_IN = 220;
  function rmSwap() {
    if (!canvas) return;
    canvas.style.transition = `opacity ${FADE_OUT}ms ease-out`;
    canvas.style.opacity = '0';
    rmFade = window.setTimeout(() => {
      shownP = Math.round(Math.max(0, Math.min(steps.length - 1, progress)));
      lastT = 0;
      draw();
      if (!canvas) return;
      canvas.style.transition = `opacity ${FADE_IN}ms ease-in`;
      canvas.style.opacity = '1';
      rmFade = 0;
      invalidate(); // the reader may have moved on again during the fade
    }, FADE_OUT);
  }
  $effect(() => () => { if (rmFade) clearTimeout(rmFade); });

  // gentle in and out within each blend, so a step never lurches as it starts or lands
  const smooth = (t: number) => t * t * (3 - 2 * t);
  let cam: Cam = { x: 0, y: 0, k: 1 };
  let blendI = 0, blendT = 0;
  const SX = (x: number) => (x - cam.x) * cam.k + (inset.left + cw - inset.right) / 2;
  const SY = (y: number) => (y - cam.y) * cam.k + (inset.top + ch - inset.bottom) / 2;
  const R = (r: number) => Math.max(1.4, r * (cam.k <= 1 ? cam.k : Math.pow(cam.k, 0.7)));

  function draw(now: number = performance.now()) {
    raf = 0;
    if (!ctx || !cw || !ch || !cams.length || !paints.length) return;
    const n = steps.length - 1;
    let target = Math.max(0, Math.min(n, progress));
    if (prefersReducedMotion()) target = Math.round(target);
    const dt = lastT ? Math.min(64, now - lastT) : 16;
    lastT = now;
    if (prefersReducedMotion()) {
      // reduced motion: nothing travels. Each step is shown finished, and a step change is a short fade (out, swap, in)
      if (shownP < 0) shownP = target;
      else if (target !== shownP && !rmFade) rmSwap();
    } else if (shownP < 0 || Math.abs(target - shownP) > 2.5) shownP = target; // first frame, cuts, big jumps
    else shownP += (target - shownP) * (1 - Math.exp(-dt / TAU));
    if (Math.abs(target - shownP) < 0.0005) shownP = target;
    let more = shownP !== target;

    blendI = Math.min(n, Math.floor(shownP));
    blendT = blendI >= n ? 0 : smooth(shownP - blendI);
    const a = cams[blendI], b = cams[Math.min(n, blendI + 1)];
    cam = {
      x: a.x + (b.x - a.x) * blendT,
      y: a.y + (b.y - a.y) * blendT,
      k: Math.exp(Math.log(a.k) + (Math.log(b.k) - Math.log(a.k)) * blendT)
    };

    vA = variantOf(stepA()); vB = variantOf(stepB());
    if (vA === vB || blendT === 0) { xyNow = vA.xy; rNow = vA.r; }
    else {
      // each dot sets off a little later the further right it ends up, so a rearrangement sweeps across instead of jumping
      const out = new Float32Array(vA.xy.length), n2 = vA.xy.length / 2, SPREAD = 0.3;
      for (let i = 0; i < n2; i++) {
        const d = (vB.xy[2 * i] / vB.w) * SPREAD;
        const t = smooth(Math.max(0, Math.min(1, (blendT - d) / (1 - SPREAD))));
        out[2 * i] = vA.xy[2 * i] + (vB.xy[2 * i] - vA.xy[2 * i]) * t;
        out[2 * i + 1] = vA.xy[2 * i + 1] + (vB.xy[2 * i + 1] - vA.xy[2 * i + 1]) * t;
      }
      xyNow = out;
      rNow = vA.r + (vB.r - vA.r) * blendT;
    }
    if (vA !== vB && blendT > 0) more = true;

    if (edges) {
      const A = stepA(), B = stepB();
      // the IMDb / Letterboxd side names always show (decoAlpha only fades the rows' own labels)
      sidesOp = lerp(A.sides === false ? 0 : 1, B.sides === false ? 0 : 1);
      const same = A.stat && B.stat && A.stat[0] === B.stat[0] && A.stat[1] === B.stat[1];
      const cur = blendT < 0.5 ? A.stat : B.stat;
      stat = cur ?? null;
      statOp = same ? 1 : Math.abs(1 - 2 * blendT);
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    drawBands();
    drawLinks();
    drawDots();
    drawDeco();
    buildTree();
    const i = shown ? layout.keys.indexOf(shown) : -1;
    tipPos = i < 0 ? null : { x: SX(xyNow[2 * i]), y: SY(xyNow[2 * i + 1]) };
    if (tipPos) readVisible();
    if (more) invalidate(); else lastT = 0;
  }

  const lerp = (p: number, q: number) => p + (q - p) * blendT;
  const stepA = () => steps[blendI], stepB = () => steps[Math.min(steps.length - 1, blendI + 1)];
  const rowOfY = (y: number) => (blendT < 0.5 ? vA : vB).rows?.find((r) => y >= r.y0 && y < r.y1)?.t ?? null;
  const rowOnIn = (s: StageStep, y: number) => { const r = rowOfY(y); return !s.focusRows || r === null || s.focusRows.includes(r); };

  // while two arrangements blend, each one's lines and labels are drawn at its own weight
  function drawDeco() {
    const sets: [V['deco'], number][] = vA === vB ? [[vA.deco, 1]] : [[vA.deco, 1 - blendT], [vB.deco, blendT]];
    for (const [d, w] of sets) drawDecoOf(d, w, 'lines');
    drawStrips();
    for (const [d, w] of sets) drawDecoOf(d, w, 'labels');
    // callouts go on top of everything in the chart, but clipped to the area between the top and bottom strips, so a
    // leader line never runs across the key or the header
    const c = ctx!;
    c.save();
    c.beginPath(); c.rect(0, inset.top - 3, cw, ch - inset.top - inset.bottom + 6); c.clip();
    drawNotes();
    c.restore();
  }

  // Spotlight: on a step that names films with callouts and focuses on some rows, every other row fades almost
  // away (dots and labels), so the callouts read cleanly even where they pass over a neighbouring row.
  const hasSpot = (s: StageStep) => (s.notes?.length && s.focusRows?.length ? 1 : 0);
  const spotNow = () => lerp(hasSpot(stepA()), hasSpot(stepB()));
  const SPOT_FADE = 0.85;
  /** alpha multiplier for something in the row at layout y */
  const spotAlpha = (spot: number, y: number) =>
    spot <= 0 ? 1 : 1 - SPOT_FADE * spot * (1 - lerp(rowOnIn(stepA(), y) ? 1 : 0, rowOnIn(stepB(), y) ? 1 : 0));

  // bands along the top (pinned header) and bottom (key), so rows passing underneath don't show through
  function drawStrips() {
    const c = ctx!;
    const deco = 1; // the header line always shows, like the IMDb / Letterboxd tags above it
    c.save();
    c.globalAlpha = 1;
    c.fillStyle = col.bg;
    c.fillRect(0, 0, cw, inset.top - 4);
    c.fillRect(0, ch - inset.bottom + 4, cw, inset.bottom - 4);
    c.fillStyle = col.line;
    c.globalAlpha = 0.9 * deco;
    c.fillRect(0, inset.top - 4, cw, 1);
    c.globalAlpha = 0.9;
    c.fillRect(0, ch - inset.bottom + 4, cw, 1);
    c.restore();
  }

  function drawDecoOf(d: V['deco'], weight: number, part: 'lines' | 'labels') {
    if (weight <= 0.01) return;
    const c = ctx!;
    const rowDeco = lerp(stepA().decoAlpha ?? 1, stepB().decoAlpha ?? 1);
    const deco = rowDeco * weight;
    c.save();
    if (part === 'lines') {
    for (const l of d.lines ?? []) {
      // benchmark marks are dashed, in the muted grey, and fade with their row when it isn't in focus
      const mirror = l.c === 'mirror';
      if (mirror) { const on = lerp(rowOnIn(stepA(), l.y1) ? 1 : 0, rowOnIn(stepB(), l.y1) ? 1 : 0); c.globalAlpha = weight * (0.3 + 0.6 * on); }
      else c.globalAlpha = weight;
      c.strokeStyle = mirror ? col.muted : col.line;
      c.lineWidth = mirror ? 1.5 : 1;
      c.setLineDash(mirror ? [3, 3] : []);
      c.beginPath();
      c.moveTo(Math.round(SX(l.x1)) + 0.5, SY(l.y1));
      c.lineTo(Math.round(SX(l.x2)) + 0.5, SY(l.y2));
      c.stroke();
    }
    c.setLineDash([]);
    c.restore();
    return;
    }

    // rank ticks beside the columns (only where they won't crowd: every tick when zoomed in, the ends when zoomed out)
    c.font = `500 12px ${col.sans}`;
    c.fillStyle = col.muted;
    c.textBaseline = 'middle';
    c.globalAlpha = deco;
    const ticks = d.yticks ?? [];
    for (const t of ticks) {
      const y = SY(t.y);
      if (y < inset.top + 6 || y > ch - inset.bottom - 6) continue;
      if (cam.k < 0.8 && !['1', '250', '500'].includes(t.v)) continue;
      c.textAlign = t.x < vA.w / 2 ? 'right' : 'left';
      c.fillText(t.v, SX(t.x), y);
    }
    c.textBaseline = 'alphabetic';
    const far = cam.k < 0.55;
    const noCounts = (blendT < 0.5 ? stepA() : stepB()).hideCounts;
    // the IMDb / Letterboxd header tags are collected and drawn after the loop, kept on screen (see drawHeadTags)
    const heads: HeadTag[] = [];
    for (const l of d.labels ?? []) {
      const cls = l.c.split(' ');
      const head = cls.includes('head'), count = cls.includes('count');
      if (count && (far || noCounts)) continue;
      if (head && edges) continue;
      // the IMDb / Letterboxd header is pinned to the top of the stage, so the sides stay named at every zoom
      // counts carry the dots' centre line as their y: centre the digits on it in screen space, so they stay level
      // with their row at every zoom (digits are about 0.72 em tall, so the baseline sits 0.36 em below the line)
      const countSize = far ? 12 : 14;
      const x = SX(l.x), y = head ? inset.top - 10 : count ? SY(l.y) + countSize * 0.36 : SY(l.y);
      // row names and counts stay inside the chart area, never on the header or footer strips
      if (!head && (y < inset.top + 10 || y > ch - inset.bottom)) continue;
      // rows in focus in full ink; context rows in the muted grey, which still clears 4.5:1 against the page
      const on = head ? 1 : lerp(rowOnIn(stepA(), l.y) ? 1 : 0, rowOnIn(stepB(), l.y) ? 1 : 0);
      c.globalAlpha = head ? weight : deco * spotAlpha(spotNow(), l.y);
      const bandLabel = cls.includes('band-label'), group = cls.includes('group'), big = cls.includes('big');
      // type scale: 12 px for every small chart label (row names, header tags, ticks), 14 px for counts in close-up views
      c.font = head || group ? `650 12px ${col.sans}` : big ? `650 30px ${col.sans}` : bandLabel ? `italic 500 12px ${col.sans}` : count ? `600 ${countSize}px ${col.sans}` : `600 12px ${col.sans}`;
      const tint = bandLabel ? col.muted : cls.includes('imdb') ? col.imdbInk : cls.includes('lb') ? col.lbInk : cls.includes('both') ? col.bothInk : col.ink;
      c.fillStyle = on >= 0.5 ? tint : col.muted;
      c.textAlign = l.a === 'middle' ? 'center' : l.a === 'end' ? 'right' : 'left';
      let text = fill(numbers, l.t);
      if (head || group || cls.includes('row')) {
        text = text.toUpperCase();
        if ('letterSpacing' in c) (c as any).letterSpacing = '0.07em';
      }
      // IMDb and Letterboxd labels and counts become brand tags: pure yellow with dark text (10:1), deep purple with
      // light text (6.8:1). Rows out of focus keep plain muted text, so the tags mark what the step is about.
      const brand = cls.includes('imdb') ? 'imdb' : cls.includes('lb') ? 'lb' : null;
      if (brand && (head || count || group || big) && on >= 0.5) {
        const size = big ? 30 : head || group ? 12 : countSize;
        const padX = big ? 9 : 5, padY = big ? 3 : 2;
        // push the text outward by the padding, so a tag never touches the dots it labels
        // counts and the two header tags are pushed outward (by the tag's padding, plus a gap for the header pair), so a
        // tag never touches the dots it labels and the IMDb / Letterboxd tags never meet across the centre line
        const push = count ? padX : head ? padX + 4 : 0;
        const tx = c.textAlign === 'right' ? x - push : c.textAlign === 'left' ? x + push : x;
        const tw = c.measureText(text).width;
        const left = c.textAlign === 'right' ? tx - tw : c.textAlign === 'center' ? tx - tw / 2 : tx;
        c.fillStyle = brand === 'imdb' ? col.imdbTag : col.lbTag;
        c.beginPath();
        // the tag box is centred on the digits (cap-height middle), not on the font's full line box
        const rh = (count ? size * 0.72 : size * 1.12) + 2 * padY + (count ? 4 : 0);
        const ry = count ? y - size * 0.36 - rh / 2 : y - size * 0.86 - padY;
        const rx = left - padX, rw = tw + 2 * padX;
        if (head) { heads.push({ text, tx, y, rx, ry, rw, rh, brand, alpha: c.globalAlpha }); if ('letterSpacing' in c) (c as any).letterSpacing = '0px'; continue; }
        if ('roundRect' in c) c.roundRect(rx, ry, rw, rh, big ? 6 : 3); else (c as CanvasRenderingContext2D).rect(rx, ry, rw, rh);
        c.fill();
        c.fillStyle = brand === 'imdb' ? col.imdbTagInk : col.lbTagInk;
        c.fillText(text, tx, y);
        if ('letterSpacing' in c) (c as any).letterSpacing = '0px';
        continue;
      }
      c.lineJoin = 'round'; c.lineWidth = 4; c.strokeStyle = col.bg;
      c.strokeText(text, x, y);
      c.fillText(text, x, y);
      if ('letterSpacing' in c) (c as any).letterSpacing = '0px';
    }
    drawHeadTags(heads);
    c.restore();
  }

  type HeadTag = { text: string; tx: number; y: number; rx: number; ry: number; rw: number; rh: number; brand: 'imdb' | 'lb'; alpha: number };
  // The header tags sit either side of the chart's centre line. When the camera pans so far that the line leaves the
  // screen (a close-up of one list's column), each tag stops at the screen edge instead of sliding off, keeping IMDb
  // before Letterboxd, and both slide back to the centre line once the view returns.
  function drawHeadTags(tags: HeadTag[]) {
    const c = ctx!, M = 6, GAP = 8;
    tags.sort((a, b) => a.rx - b.rx);
    let cursor = M;
    for (const t of tags) { const dx = Math.max(0, cursor - t.rx); t.rx += dx; t.tx += dx; cursor = t.rx + t.rw + GAP; }
    cursor = cw - M;
    for (let i = tags.length - 1; i >= 0; i--) {
      const t = tags[i], dx = Math.max(0, t.rx + t.rw - cursor);
      t.rx -= dx; t.tx -= dx; cursor = t.rx - GAP;
    }
    c.font = `650 12px ${col.sans}`;
    if ('letterSpacing' in c) (c as any).letterSpacing = '0.07em';
    for (const t of tags) {
      c.globalAlpha = t.alpha;
      c.fillStyle = t.brand === 'imdb' ? col.imdbTag : col.lbTag;
      c.beginPath();
      if ('roundRect' in c) c.roundRect(t.rx, t.ry, t.rw, t.rh, 3); else (c as CanvasRenderingContext2D).rect(t.rx, t.ry, t.rw, t.rh);
      c.fill();
      c.fillStyle = t.brand === 'imdb' ? col.imdbTagInk : col.lbTagInk;
      c.textAlign = 'left';
      c.fillText(t.text, t.rx + (t.rw - c.measureText(t.text).width) / 2, t.y);
    }
    if ('letterSpacing' in c) (c as any).letterSpacing = '0px';
  }

  function drawBands() {
    const c = ctx!;
    for (const r of (blendT < 0.5 ? vA : vB).deco.rects ?? []) {
      c.globalAlpha = 1;
      c.fillStyle = col.band;
      c.fillRect(SX(r.x), SY(r.y), r.w * cam.k, r.h * cam.k);
    }
  }

  function drawLinks() {
    if (!pairs.length || !linkPaints.length) return;
    const c = ctx!, xy = xyNow;
    const la = linkPaints[blendI], lb = linkPaints[Math.min(linkPaints.length - 1, blendI + 1)];
    c.save();
    c.lineCap = 'round';
    pairs.forEach((p, j) => {
      const a = la.alpha[j] + (lb.alpha[j] - la.alpha[j]) * blendT;
      if (a <= 0.01) return;
      const w = la.width[j] + (lb.width[j] - la.width[j]) * blendT || 1;
      // colour blends between the two steps; a line only one step draws keeps that step's colour while it fades
      const channel = (o: number) => {
        const from = la.alpha[j] > 0 ? la.rgb[3 * j + o] : lb.rgb[3 * j + o];
        const to = lb.alpha[j] > 0 ? lb.rgb[3 * j + o] : la.rgb[3 * j + o];
        return Math.round(from + (to - from) * blendT);
      };
      c.globalAlpha = a;
      c.strokeStyle = `rgb(${channel(0)},${channel(1)},${channel(2)})`;
      c.lineWidth = w;
      const x1 = SX(xy[2 * p.a]), y1 = SY(xy[2 * p.a + 1]), x2 = SX(xy[2 * p.b]), y2 = SY(xy[2 * p.b + 1]);
      if ((y1 < 0 && y2 < 0) || (y1 > ch && y2 > ch)) return;
      c.beginPath();
      c.moveTo(x1, y1);
      const mx = (x1 + x2) / 2;
      c.bezierCurveTo(mx, y1, mx, y2, x2, y2);
      c.stroke();
    });
    c.restore();
  }

  function drawDots() {
    const c = ctx!, xy = xyNow, n = layout.keys.length, r = R(rNow);
    const pa = paints[blendI], pb = paints[Math.min(paints.length - 1, blendI + 1)];
    const focusId = shown ? parseKey(shown).id : null;
    const spot = spotNow();
    // two passes: faded dots first, then full-strength ones on top, so a highlighted dot is never covered by a neighbour
    for (let pass = 0; pass < 2; pass++)
    for (let i = 0; i < n; i++) {
      const a = pa.alpha[i] + (pb.alpha[i] - pa.alpha[i]) * blendT;
      if (a <= 0.01 || (pass === 0) !== (a < 0.99)) continue;
      const x = SX(xy[2 * i]), y = SY(xy[2 * i + 1]);
      if (x < -r || y < -r || x > cw + r || y > ch + r) continue;
      const same = focusId !== null && parseKey(layout.keys[i]).id === focusId;
      const R_ = Math.round(pa.rgb[3 * i] + (pb.rgb[3 * i] - pa.rgb[3 * i]) * blendT);
      const G_ = Math.round(pa.rgb[3 * i + 1] + (pb.rgb[3 * i + 1] - pa.rgb[3 * i + 1]) * blendT);
      const B_ = Math.round(pa.rgb[3 * i + 2] + (pb.rgb[3 * i + 2] - pa.rgb[3 * i + 2]) * blendT);
      c.globalAlpha = a * (focusId !== null && !same ? 0.45 : 1) * spotAlpha(spot, xy[2 * i + 1]);
      c.beginPath();
      c.arc(x, y, same ? r + 1.5 : r, 0, Math.PI * 2);
      c.fillStyle = `rgb(${R_},${G_},${B_})`;
      c.fill();
      const st = blendT < 0.5 ? pa.stroke[i] : pb.stroke[i];
      if (st && r > 1.6) { c.strokeStyle = st; c.lineWidth = r > 3 ? 1 : 0.6; c.stroke(); }
      else if (r >= 2.4) { c.strokeStyle = col.bg; c.lineWidth = r > 4 ? 1.2 : 0.8; c.stroke(); }
      if (same) {
        c.beginPath(); c.arc(x, y, r + 4.5, 0, Math.PI * 2);
        c.strokeStyle = col.ink; c.lineWidth = 1.5; c.globalAlpha = 1; c.stroke();
      }
    }
    c.globalAlpha = 1;
  }

  function drawNotes() {
    const same = stepA() === stepB();
    const sets: [StageNote[], number][] = same ? [[stepA().notes ?? [], 1]] : [[stepA().notes ?? [], 1 - blendT], [stepB().notes ?? [], blendT]];
    const c = ctx!, r = R(rNow);
    c.save();
    for (const [notes, alpha] of sets) {
      if (alpha < 0.02) continue;
      for (const n of notes) {
        const i = layout.keys.indexOf(n.key);
        if (i < 0) continue;
        const px = SX(xyNow[2 * i]), py = SY(xyNow[2 * i + 1]);
        // a callout only shows while its dot is in the visible chart area (not under the cards, header or key)
        if (py < inset.top || py > ch - inset.bottom || px < inset.left - 8 || px > cw - inset.right + 8) continue;
        c.globalAlpha = alpha;
        let left = n.dx < 0;
        let title = narrowNow && n.titleNarrow ? n.titleNarrow : n.title;
        c.font = `650 14px ${col.sans}`;
        let tw = Math.max(c.measureText(title).width, n.text ? (c.font = `14px ${col.sans}`, c.measureText(n.text).width) : 0);
        const place = (l: boolean, dx: number) => (l ? Math.max(inset.left + tw + 8, px + dx) : Math.min(cw - inset.right - tw - 8, px + dx));
        let tx = place(left, n.dx);
        // a label on the dot's own line (small dy) that doesn't fit on its side would be pushed over the dot: it moves
        // to the other side instead, when there's room there
        if (Math.abs(n.dy) < 20 && (left ? tx + 5 > px : tx - 5 < px)) {
          const alt = place(!left, -n.dx);
          if (!left ? alt + 5 <= px : alt - 5 >= px) { left = !left; tx = alt; }
          else if (!n.text) {
            // no room on either side: shorten the title to fit beside the dot (drop a leading "The", then trim the name
            // with an ellipsis, keeping anything after " · ", e.g. the rank)
            const room = left ? px + n.dx - inset.left - 8 : cw - inset.right - 8 - (px + n.dx);
            c.font = `650 14px ${col.sans}`;
            const cut = title.indexOf(' · ');
            let name = (cut < 0 ? title : title.slice(0, cut)).replace(/^The /, ''), tail = cut < 0 ? '' : title.slice(cut);
            const fit = (t: string) => c.measureText(t).width <= room;
            if (!fit(name + tail)) {
              while (name.length > 3 && !fit(name.trimEnd() + '…' + tail)) name = name.slice(0, -1);
              name = name.trimEnd() + '…';
            }
            title = name + tail;
            tw = c.measureText(title).width;
            tx = place(left, n.dx);
          }
        }
        const ty = Math.max(inset.top + 14, Math.min(ch - inset.bottom - 24, py + n.dy));
        // the label block and a soft plate behind it in the page colour, so whatever lies under the callout drops away;
        // the plate goes down first so it never covers the leader line
        const bx = (left ? tx - tw : tx) - 6, by = ty - 16, bh = n.text ? 43 : 23, bw = tw + 12;
        c.fillStyle = col.bg;
        c.globalAlpha = alpha * 0.88;
        c.beginPath();
        if ('roundRect' in c) c.roundRect(bx, by, bw, bh, 5); else (c as CanvasRenderingContext2D).rect(bx, by, bw, bh);
        c.fill();
        c.globalAlpha = alpha;
        // the leader runs from the dot to the label: to its inner side when the label sits clear to one side of the dot;
        // otherwise (a long title pushed over the dot) to the start of the title: just under its first word when the dot
        // is below, just over it when the dot is above
        const clear = left ? tx + 5 <= px : tx - 5 >= px; // the label ends before the dot's centre
        c.font = `650 14px ${col.sans}`;
        const titleStart = left ? tx - c.measureText(title).width : tx;
        const firstWord = c.measureText(title.split(' ')[0]).width;
        const ex = clear ? (left ? tx + 5 : tx - 5) : titleStart + firstWord / 2;
        const ey = clear ? ty - 4 : py > ty ? ty + 5 : ty - 17;
        const ang = Math.atan2(ey - py, ex - px);
        c.beginPath();
        c.moveTo(px + Math.cos(ang) * (r + 3), py + Math.sin(ang) * (r + 3));
        c.lineTo(ex, ey);
        c.strokeStyle = col.ink; c.lineWidth = 1; c.stroke();
        c.textAlign = left ? 'right' : 'left';
        c.textBaseline = 'alphabetic';
        c.lineJoin = 'round'; c.lineWidth = 4; c.strokeStyle = col.bg;
        c.font = `650 14px ${col.sans}`;
        c.strokeText(title, tx, ty); c.fillStyle = col.ink; c.fillText(title, tx, ty);
        if (n.text) {
          c.font = `14px ${col.sans}`;
          c.strokeText(n.text, tx, ty + 18); c.fillStyle = col.muted; c.fillText(n.text, tx, ty + 18);
        }
      }
    }
    c.restore();
  }

  // ---------------------------------------------------------------- hover and tap
  let tree: Quadtree<number> | null = null;
  let hovered = $state<string | null>(null);
  let tipPos = $state<{ x: number; y: number } | null>(null);
  const shown = $derived(hovered ?? selected);
  $effect(() => { void shown; invalidate(); });

  function buildTree() {
    const pa = paints[blendI], pb = paints[Math.min(paints.length - 1, blendI + 1)];
    const pts: number[] = [];
    for (let i = 0; i < layout.keys.length; i++) if (pa.alpha[i] + (pb.alpha[i] - pa.alpha[i]) * blendT > 0.6) pts.push(i);
    tree = quadtree<number>().x((i) => SX(xyNow[2 * i])).y((i) => SY(xyNow[2 * i + 1])).addAll(pts);
  }

  let lastPointer = 'mouse';
  function pick(ev: MouseEvent, slop: number) {
    if (!tree) return null;
    const rect = canvas.getBoundingClientRect();
    const i = tree.find(ev.clientX - rect.left, ev.clientY - rect.top, slop);
    return i === undefined ? null : layout.keys[i];
  }
  function onMove(ev: PointerEvent) {
    if (ev.pointerType === 'touch') return;
    const key = pick(ev, R(rNow) + 4);
    if (key !== hovered) hovered = key;
    canvas.style.cursor = key ? 'pointer' : 'default';
  }
  function onClick(ev: MouseEvent) {
    // a fingertip is about 44 px across, so taps search a wider radius than the mouse
    const key = pick(ev, lastPointer === 'touch' ? 22 : R(rNow) + 4);
    selected = key === selected ? null : key;
    if (lastPointer === 'touch') hovered = null;
  }

  onMount(() => {
    ctx = canvas.getContext('2d');
    col = {
      ink: token('--ink'), muted: token('--muted'), line: token('--line'), bg: token('--bg'),
      imdbInk: token('--imdb-ink'), lbInk: token('--lb-ink'), bothInk: token('--both-ink'),
      imdbTag: token('--imdb-tag'), imdbTagInk: token('--imdb-tag-ink'), lbTag: token('--lb-tag'), lbTagInk: token('--lb-tag-ink'), sans: token('--sans'), display: token('--display'), band: 'rgba(31, 30, 27, 0.05)'
    };
    document.fonts?.ready.then(invalidate);
    invalidate();
  });
  onDestroy(() => { if (raf) cancelAnimationFrame(raf); });

  // the film card opens beside the dot and always fits wholly on screen: inside the stage, inside the part of the stage
  // the viewport shows, and clear of the caption column on wide screens (inset.left). It tries the four corners around
  // the dot (beside it, never over it) and takes the first that fits; if none does, it is clamped into view.
  let stageEl = $state<HTMLDivElement>();
  let tipW = $state(0), tipH = $state(0);
  let visTop = $state(0), visBot = $state(0);
  function readVisible() {
    if (!stageEl) return;
    const r = stageEl.getBoundingClientRect();
    visTop = Math.max(0, -r.top);
    visBot = Math.min(ch, window.innerHeight - r.top);
  }
  const tipStyle = $derived.by(() => {
    if (!tipPos) return '';
    const G = 8, OFF = 14;
    const w = tipW || Math.min(300, cw - 16), h = tipH || 150;
    const x0 = Math.max(G, Math.min(inset.left - 12, cw - w - G)), x1 = cw - G;
    const y0 = visTop + G, y1 = (visBot || ch) - G;
    const fits = (l: number, t: number) => l >= x0 && l + w <= x1 && t >= y0 && t + h <= y1;
    const rightX = tipPos.x + OFF, leftX = tipPos.x - OFF - w, belowY = tipPos.y + OFF, aboveY = tipPos.y - OFF - h;
    const preferRight = tipPos.x <= cw * 0.55, preferBelow = tipPos.y - visTop < (y1 - y0) * 0.5;
    const xs = preferRight ? [rightX, leftX] : [leftX, rightX];
    const ys = preferBelow ? [belowY, aboveY] : [aboveY, belowY];
    let pick: [number, number] | null = null;
    for (const t of ys) for (const l of xs) if (!pick && fits(l, t)) pick = [l, t];
    // nothing fits beside the dot (a small phone): keep it on screen, centred across, above or below the dot
    if (!pick) {
      const l = Math.max(x0, Math.min(x1 - w, tipPos.x - w / 2));
      const t = belowY + h <= y1 ? belowY : aboveY >= y0 ? aboveY : Math.max(y0, Math.min(y1 - h, belowY));
      pick = [l, t];
    }
    return `left:${Math.round(pick[0])}px;top:${Math.round(pick[1])}px`;
  });
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape') selected = null; }} />

<div class="stage" bind:this={stageEl} bind:clientWidth={cw} bind:clientHeight={ch}>
  <canvas
    bind:this={canvas}
    aria-hidden="true"
    style:width="{cw}px"
    style:height="{ch}px"
    onpointermove={onMove}
    onpointerleave={() => (hovered = null)}
    onpointerdown={(e) => (lastPointer = e.pointerType)}
    onclick={onClick}
  ></canvas>
  {#if edges}
    <!-- each side named at its own edge of the chart, with the step's key number under it (the cards say the same in words) -->
    <div class="sides" aria-hidden="true" style:opacity={sidesOp} style:left="{inset.left}px" style:right="{inset.right}px" style:height="{inset.top - 14}px">
      <div class="side imdb">
        <span class="name tag imdb">← IMDb</span>
        {#if stat}<span class="num tag imdb" style:opacity={statOp}>{stat[0]}</span>{/if}
      </div>
      <div class="side lb">
        <span class="name tag lb">Letterboxd →</span>
        {#if stat}<span class="num tag lb" style:opacity={statOp}>{stat[1]}</span>{/if}
      </div>
    </div>
  {/if}
  {#if tip && shown && tipPos}
    <div class="tip" class:pinned={selected === shown} style={tipStyle} bind:offsetWidth={tipW} bind:offsetHeight={tipH}>
      {@render tip(shown)}
      {#if selected === shown}<button type="button" class="close" aria-label="Close the film card" onclick={() => (selected = null)}>×</button>{/if}
    </div>
  {/if}
</div>

<style>
  .stage { position: absolute; inset: 0; overflow: hidden; }
  canvas { display: block; touch-action: pan-y; -webkit-tap-highlight-color: transparent; }
  .tip {
    position: absolute; z-index: 4; width: min(300px, calc(100% - 16px));
    background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 40px 10px 12px;
    font: 14px/1.4 var(--sans); box-shadow: 0 8px 28px rgba(31, 30, 27, 0.14); pointer-events: none;
  }
  .tip.pinned { pointer-events: auto; }
  .sides { position: absolute; top: 14px; display: flex; justify-content: space-between; align-items: flex-start; pointer-events: none; }
  .side { display: grid; gap: 8px; justify-items: start; }
  .side.lb { justify-items: end; }
  .name { font: 650 12px var(--sans); letter-spacing: 0.08em; text-transform: uppercase; padding: 3px 9px; }
  /* Inter, not the display serif: numbers read faster in the sans, especially inside a tag */
  .num { font: 650 clamp(32px, 3.4vw, 46px)/1.1 var(--sans); letter-spacing: -0.02em; font-variant-numeric: tabular-nums; padding: 2px 12px 3px; border-radius: 8px; }
  /* 44 px hit area (Apple HIG; Material asks 48 dp, WCAG 2.2 at least 24 px) */
  .close {
    position: absolute; top: 0; right: 0; width: 44px; height: 44px; border: 0; background: none;
    font-size: 20px; line-height: 1; cursor: pointer; color: var(--muted);
  }
</style>

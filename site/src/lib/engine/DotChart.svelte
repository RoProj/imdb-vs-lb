<!--
  The one dot renderer used by every dot chart, in Read mode, Tour mode and the explorer.
  - Canvas drawing (one element for all dots); the dot under the pointer is found with a quadtree.
  - Geometric zoom: positions spread apart, dots keep their size. Zoom rules live in zoom.ts (never traps page scroll).
  - Motion: dots rise into place the first time the chart scrolls into view, and glide (staggered left to right)
    when the layout changes. Reduced-motion readers get no motion.
  - Hover or tap brings one film forward: its dots grow, everything else fades back, its links darken.
  - Film names appear as you zoom in; keys in `always` are labelled at every zoom level.
-->
<script lang="ts" module>
  export interface DotStyle { fill: string; stroke?: string; alpha?: number }
  /** A link is drawn in one colour, or as a gradient from its first end (`from`) to its second end (`to`). */
  export interface LinkStyle { color?: string; from?: string; to?: string; alpha: number; width: number }
  /** A callout: a short title (and optional second line) joined to a dot by a leader line.
   *  dx/dy: offset of the text from the dot in px; `narrow` overrides it on phones (false hides the note). */
  export interface Note { key: string; title: string; text?: string; dx: number; dy: number; narrow?: { dx: number; dy: number } | false }
</script>

<script lang="ts">
  import { onDestroy, onMount, type Snippet } from 'svelte';
  import { quadtree, type Quadtree } from 'd3-quadtree';
  import { zoomIdentity, type ZoomTransform } from 'd3-zoom';
  import { attachZoom, zoomHintText, type ZoomApi } from './zoom';
  import { fill, parseKey, token, prefersReducedMotion, type Layout, type Numbers, type Variant } from '$lib/data';

  interface Props {
    layout: Layout;
    style: (key: string, i: number) => DotStyle;
    links?: [number, number][];
    linkStyle?: (a: number, b: number) => LinkStyle | null;
    curved?: boolean;
    label?: (key: string) => string;
    always?: string[];
    tip?: Snippet<[string]>;
    selected?: string | null;
    hovered?: string | null;
    zoomable?: boolean;
    maxZoom?: number;
    labelZoom?: number;
    numbers?: Numbers | null;
    ariaLabel: string;
    narrowBelow?: number;
    intro?: 'rise' | 'none';
    notes?: Note[];
    source?: string;
    children?: Snippet;
  }
  let {
    layout, style, links = [], linkStyle, curved = false, label = (k) => k, always = [], tip,
    selected = $bindable(null), hovered = $bindable(null), zoomable = true, maxZoom = 10, labelZoom = 2.2,
    numbers = null, ariaLabel, narrowBelow = 560, intro = 'rise', notes = [], source = '', children
  }: Props = $props();

  let canvas: HTMLCanvasElement;
  let plotEl: HTMLDivElement;
  let cw = $state(0);
  const variant: Variant = $derived(cw && cw < narrowBelow ? layout.narrow : layout.wide);
  const s = $derived(cw ? cw / variant.w : 1);
  const ch = $derived(Math.round(variant.h * s));

  // drawing state (not reactive: the canvas is redrawn on demand)
  let ctx: CanvasRenderingContext2D | null = null;
  let dpr = 1;
  let t: ZoomTransform = zoomIdentity;
  let k = $state(1);
  let keys: string[] = [];
  let ids: string[] = [];
  let index = new Map<string, number>();
  let cur = new Float32Array(0), from = new Float32Array(0), tgt = new Float32Array(0), delay = new Float32Array(0);
  let radii = new Float32Array(0);
  let fills: string[] = [], strokes: (string | undefined)[] = [], alphas = new Float32Array(0);
  let animStart = 0, animDur = 0, animSpan = 0, fade = 1;
  let lastLayout: Layout | null = null, lastVariant: Variant | null = null;
  let tree: Quadtree<number> | null = null;
  let raf = 0;
  let zoomApi: ZoomApi | null = null;
  let seen = false; // becomes true when the intro starts (or at mount when intro is 'none')
  let col: Record<string, string> = {};
  let lastPointer = 'mouse';

  let hint = $state('');
  let hintTimer: ReturnType<typeof setTimeout> | undefined;
  let tipPos = $state<{ x: number; y: number } | null>(null);
  const shown = $derived(hovered ?? selected);
  const focusId = $derived(shown ? (parseKey(shown).id ?? shown) : null);

  const invalidate = () => { if (!raf && typeof requestAnimationFrame !== 'undefined') raf = requestAnimationFrame(draw); };

  function startAnim(stagger: number, dur: number) {
    // stagger: each dot waits in proportion to its target x, so the change sweeps left to right
    delay = new Float32Array(keys.length);
    for (let i = 0; i < keys.length; i++) delay[i] = cw ? (tgt[2 * i] / cw) * stagger : 0;
    animStart = performance.now();
    animDur = dur;
    animSpan = dur + stagger;
  }

  function setTarget(lay: Layout, v: Variant, sc: number) {
    const n = lay.keys.length;
    const next = new Float32Array(2 * n);
    for (let i = 0; i < 2 * n; i++) next[i] = v.xy[i] * sc;
    const rr = new Float32Array(n);
    for (let i = 0; i < n; i++) rr[i] = Math.max(1.2, (v.radii?.[i] ?? v.r) * sc);
    const switched = lastLayout !== null && (lay !== lastLayout || v !== lastVariant);
    const motion = !prefersReducedMotion();
    if (switched && motion && seen) {
      const prev = new Map<string, [number, number]>();
      keys.forEach((key, i) => prev.set(key, [cur[2 * i], cur[2 * i + 1]]));
      from = new Float32Array(2 * n);
      lay.keys.forEach((key, i) => {
        const p = prev.get(key);
        from[2 * i] = p ? p[0] : next[2 * i];
        from[2 * i + 1] = p ? p[1] : next[2 * i + 1];
      });
    } else {
      from = next.slice();
    }
    if (lay !== lastLayout) zoomApi?.reset(false);
    keys = lay.keys;
    ids = keys.map((key) => parseKey(key).id ?? key);
    index = new Map(keys.map((key, i) => [key, i]));
    tgt = next;
    cur = from.slice();
    radii = rr;
    if (switched && motion && seen) startAnim(320, 750);
    else animDur = 0;
    lastLayout = lay;
    lastVariant = v;
    invalidate();
  }

  /** First time the chart is seen: dots rise from below their place, sweeping left to right. */
  function playIntro() {
    seen = true;
    if (prefersReducedMotion() || !keys.length) { fade = 1; invalidate(); return; }
    from = tgt.slice();
    for (let i = 0; i < keys.length; i++) from[2 * i + 1] = tgt[2 * i + 1] + 26 * s + 10;
    cur = from.slice();
    fade = 0;
    startAnim(550, 700);
    invalidate();
  }

  $effect(() => {
    const lay = layout, v = variant, sc = s;
    if (cw) setTarget(lay, v, sc);
  });

  $effect(() => {
    const ks = layout.keys;
    const f: string[] = [], st: (string | undefined)[] = [], al = new Float32Array(ks.length);
    ks.forEach((key, i) => {
      const d = style(key, i);
      f.push(d.fill); st.push(d.stroke); al[i] = d.alpha ?? 1;
    });
    fills = f; strokes = st; alphas = al;
    invalidate();
  });

  $effect(() => { void always; void links; void linkStyle; void shown; void numbers; void notes; invalidate(); });

  $effect(() => {
    if (!canvas || !cw) return;
    dpr = Math.min(2.5, window.devicePixelRatio || 1);
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
    canvas.style.width = `${cw}px`;
    canvas.style.height = `${ch}px`;
    zoomApi?.resize(cw, ch);
    invalidate();
  });

  const ease = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const X = (x: number) => x * t.k + t.x;
  const Y = (y: number) => y * t.k + t.y;

  function draw() {
    raf = 0;
    if (!ctx || !cw) return;
    let animating = false;
    if (animDur) {
      const now = performance.now() - animStart;
      for (let i = 0; i < keys.length; i++) {
        const e = ease(Math.min(1, Math.max(0, (now - delay[i]) / animDur)));
        cur[2 * i] = from[2 * i] + (tgt[2 * i] - from[2 * i]) * e;
        cur[2 * i + 1] = from[2 * i + 1] + (tgt[2 * i + 1] - from[2 * i + 1]) * e;
      }
      fade = Math.min(1, Math.max(fade, now / (animSpan * 0.6)));
      if (now < animSpan) animating = true; else { animDur = 0; fade = 1; }
    } else if (cur.length !== tgt.length || (cur.length && cur[0] !== tgt[0])) {
      cur = tgt.slice();
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    if (!seen) return;
    drawDeco();
    drawLinks();
    drawDots();
    drawLabels();
    drawNotes();
    buildTree();
    updateTip();
    if (animating) invalidate();
  }

  const FONTS: Record<string, (c: Record<string, string>) => string> = {
    head: (c) => `650 11.5px ${c.sans}`,
    big: (c) => `500 30px ${c.display}`,
    mid: (c) => `500 20px ${c.display}`,
    row: (c) => `500 12.5px ${c.sans}`,
    median: (c) => `600 12px ${c.sans}`,
    sub: (c) => `12px ${c.sans}`,
    quad: (c) => `500 12px ${c.sans}`,
    'axis-title': (c) => `500 12px ${c.sans}`
  };

  function drawDeco() {
    const d = variant.deco, c = ctx!;
    c.save();
    c.globalAlpha = fade;
    for (const r of d.rects ?? []) {
      c.fillStyle = r.c === 'band' ? col.band : col.grid;
      c.fillRect(X(r.x * s), Y(r.y * s), r.w * s * t.k, r.h * s * t.k);
    }
    for (const l of d.lines ?? []) {
      c.beginPath();
      c.strokeStyle = l.c === 'grid' ? col.grid : l.c === 'ref' || l.c === 'median' ? col.ink : l.c === 'median-imdb' ? col.imdbEdge : l.c === 'median-lb' ? col.lbEdge : col.line;
      c.globalAlpha = fade * (l.c === 'ref' ? 0.35 : 1);
      c.lineWidth = l.c.startsWith('median') ? 1.5 : 1;
      c.setLineDash(l.c === 'ref' ? [3, 4] : []);
      c.moveTo(X(l.x1 * s), Y(l.y1 * s));
      c.lineTo(X(l.x2 * s), Y(l.y2 * s));
      c.stroke();
    }
    c.setLineDash([]);
    c.globalAlpha = fade;
    c.font = `500 12px ${col.sans}`;
    c.fillStyle = col.muted;
    c.textAlign = 'center';
    c.textBaseline = 'top';
    c.strokeStyle = col.line;
    c.lineWidth = 1;
    for (const tk of d.xticks ?? []) {
      const x = X(tk.x * s);
      if (x < -20 || x > cw + 20) continue;
      const y = Math.min(ch - 14, Math.max(6, Y(tk.y * s)));
      c.beginPath();
      c.moveTo(Math.round(x) + 0.5, y - 6);
      c.lineTo(Math.round(x) + 0.5, y - 2);
      c.stroke();
      c.fillText(tk.v, x, y + 1);
    }
    c.textAlign = 'right';
    c.textBaseline = 'middle';
    for (const tk of d.yticks ?? []) {
      const y = Y(tk.y * s);
      if (y < -10 || y > ch + 10) continue;
      c.fillText(tk.v, Math.max(24, X(tk.x * s)), y);
    }
    for (const l of d.labels ?? []) {
      const cls = l.c.split(' ');
      const kind = cls.find((x) => FONTS[x]) ?? 'sub';
      c.font = FONTS[kind](col);
      const tint = cls.includes('imdb') ? col.imdbInk : cls.includes('lb') ? col.lbInk : cls.includes('both') ? col.bothInk : null;
      c.fillStyle = tint ?? (kind === 'sub' || kind === 'axis-title' || kind === 'quad' ? col.muted : col.ink);
      c.textAlign = l.a === 'middle' ? 'center' : l.a === 'end' ? 'right' : 'left';
      c.textBaseline = 'alphabetic';
      let text = fill(numbers, l.t);
      if (kind === 'head') {
        text = text.toUpperCase();
        if ('letterSpacing' in c) (c as any).letterSpacing = '0.08em';
      }
      c.fillText(text, X(l.x * s), Y(l.y * s));
      if ('letterSpacing' in c) (c as any).letterSpacing = '0px';
    }
    c.restore();
  }

  function drawLinks() {
    if (!links.length || !linkStyle) return;
    const c = ctx!;
    const ordered = focusId ? [...links].sort((a, b) => Number(ids[a[0]] === focusId) - Number(ids[b[0]] === focusId)) : links;
    for (const [a, b] of ordered) {
      const ls = linkStyle(a, b);
      if (!ls) continue;
      const x1 = X(cur[2 * a]), y1 = Y(cur[2 * a + 1]), x2 = X(cur[2 * b]), y2 = Y(cur[2 * b + 1]);
      const on = focusId !== null && ids[a] === focusId;
      c.globalAlpha = fade * (focusId && !on ? ls.alpha * 0.35 : on ? 1 : ls.alpha);
      if (ls.from && ls.to && !on) {
        const g = c.createLinearGradient(x1, y1, x2, y2);
        g.addColorStop(0, ls.from);
        g.addColorStop(1, ls.to);
        c.strokeStyle = g;
      } else c.strokeStyle = on ? col.ink : ls.color ?? col.line;
      c.lineWidth = on ? Math.max(1.8, ls.width) : ls.width;
      c.beginPath();
      c.moveTo(x1, y1);
      if (curved) {
        const mx = (x1 + x2) / 2;
        c.bezierCurveTo(mx, y1, mx, y2, x2, y2);
      } else c.lineTo(x2, y2);
      c.stroke();
    }
    c.globalAlpha = 1;
  }

  function dotPath(c: CanvasRenderingContext2D, x: number, y: number, r: number, sq: boolean) {
    c.beginPath();
    if (sq) {
      if ('roundRect' in c) c.roundRect(x - r, y - r, 2 * r, 2 * r, Math.min(2.5, r * 0.35));
      else (c as CanvasRenderingContext2D).rect(x - r, y - r, 2 * r, 2 * r);
    } else c.arc(x, y, r, 0, Math.PI * 2);
  }

  function drawDots() {
    const c = ctx!, sq = layout.shape === 'square';
    const focus: number[] = [];
    for (let i = 0; i < keys.length; i++) {
      if (focusId !== null && ids[i] === focusId) { focus.push(i); continue; }
      const x = X(cur[2 * i]), y = Y(cur[2 * i + 1]), r = radii[i];
      if (x < -r || y < -r || x > cw + r || y > ch + r || alphas[i] === 0) continue;
      c.globalAlpha = fade * alphas[i] * (focusId !== null ? 0.28 : 1);
      dotPath(c, x, y, r, sq);
      c.fillStyle = fills[i];
      c.fill();
      if (strokes[i]) {
        c.strokeStyle = strokes[i]!;
        c.lineWidth = r > 3 ? 1 : 0.75;
        c.stroke();
      } else if (r >= 2.4) {
        // a thin halo in the page colour keeps neighbouring dots crisp in dense clusters
        c.strokeStyle = col.bg;
        c.lineWidth = r > 4 ? 1.2 : 0.8;
        c.stroke();
      }
    }
    // the focused film is drawn last, larger, with a ring
    c.globalAlpha = 1;
    for (const i of focus) {
      const x = X(cur[2 * i]), y = Y(cur[2 * i + 1]), r = radii[i] + (sq ? 1 : 2);
      dotPath(c, x, y, r, sq);
      c.fillStyle = fills[i];
      c.fill();
      if (strokes[i]) { c.strokeStyle = strokes[i]!; c.lineWidth = 1; c.stroke(); }
      dotPath(c, x, y, r + 3, sq);
      c.strokeStyle = col.ink;
      c.lineWidth = 1.5;
      c.stroke();
    }
  }

  function drawLabels() {
    const c = ctx!;
    c.font = `500 11px ${col.sans}`;
    c.textBaseline = 'middle';
    c.textAlign = 'left';
    c.globalAlpha = fade;
    const boxes: [number, number, number, number][] = [];
    const hits = (bx: [number, number, number, number]) =>
      bx[0] < 0 || bx[2] > cw || bx[1] < 0 || bx[3] > ch || boxes.some((b) => !(bx[2] < b[0] || bx[0] > b[2] || bx[3] < b[1] || bx[1] > b[3]));
    const place = (i: number, force: boolean) => {
      const px = X(cur[2 * i]), py = Y(cur[2 * i + 1]), r = radii[i];
      const text = label(keys[i]);
      const tw = c.measureText(text).width;
      // try right, left, above, below; labels the story insists on take the first free spot, or the right if none is free
      const spots: [number, number][] = [[px + r + 4, py], [px - r - 4 - tw, py], [px - tw / 2, py - r - 9], [px - tw / 2, py + r + 9]];
      let chosen: [number, number] | null = null;
      for (const [x, y] of spots) if (!hits([x - 2, y - 7, x + tw + 2, y + 7])) { chosen = [x, y]; break; }
      if (!chosen) { if (!force) return; chosen = spots[0]; }
      const [x, y] = chosen;
      boxes.push([x - 2, y - 7, x + tw + 2, y + 7]);
      c.lineWidth = 4;
      c.lineJoin = 'round';
      c.strokeStyle = col.bg;
      c.strokeText(text, x, y);
      c.fillStyle = col.ink;
      c.fillText(text, x, y);
    };
    for (const key of always) {
      const i = index.get(key);
      if (i !== undefined && alphas[i] > 0 && (focusId === null || ids[i] === focusId)) place(i, true);
    }
    if (t.k < labelZoom) return;
    let n = 0;
    for (let i = 0; i < keys.length && n < 160; i++) {
      if (alphas[i] < 0.5 || (focusId !== null && ids[i] !== focusId)) continue;
      const x = X(cur[2 * i]), y = Y(cur[2 * i + 1]);
      if (x < 0 || y < 0 || x > cw || y > ch) continue;
      place(i, false);
      n++;
    }
  }

  function drawNotes() {
    if (!notes.length) return;
    const c = ctx!, narrow = cw < narrowBelow;
    c.save();
    c.textBaseline = 'alphabetic';
    for (const n of notes) {
      const i = index.get(n.key);
      if (i === undefined) continue;
      const off = narrow ? n.narrow : { dx: n.dx, dy: n.dy };
      if (off === false) continue;
      const o = off ?? { dx: n.dx, dy: n.dy };
      const px = X(cur[2 * i]), py = Y(cur[2 * i + 1]), r = radii[i];
      if (px < 0 || py < 0 || px > cw || py > ch) continue;
      const dim = focusId !== null && ids[i] !== focusId;
      c.globalAlpha = fade * (dim ? 0.25 : 1);
      const left = o.dx < 0;
      c.font = `650 12.5px ${col.sans}`;
      const tw1 = c.measureText(n.title).width;
      c.font = `12px ${col.sans}`;
      const tw2 = n.text ? c.measureText(n.text).width : 0;
      const tw = Math.max(tw1, tw2);
      // keep the text inside the frame
      let tx = px + o.dx;
      if (left) tx = Math.max(tw + 4, tx); else tx = Math.min(cw - tw - 4, tx);
      const ty = Math.max(14, Math.min(ch - (n.text ? 20 : 6), py + o.dy));
      // leader: from the dot's edge to the near side of the text
      const ex = left ? tx + 4 : tx - 4, ey = ty - 4;
      const ang = Math.atan2(ey - py, ex - px);
      c.beginPath();
      c.moveTo(px + Math.cos(ang) * (r + 2.5), py + Math.sin(ang) * (r + 2.5));
      c.lineTo(ex, ey);
      c.strokeStyle = col.ink;
      c.lineWidth = 0.9;
      c.stroke();
      c.textAlign = left ? 'right' : 'left';
      c.lineJoin = 'round';
      c.lineWidth = 4;
      c.strokeStyle = col.bg;
      c.font = `650 12.5px ${col.sans}`;
      c.strokeText(n.title, tx, ty);
      c.fillStyle = col.ink;
      c.fillText(n.title, tx, ty);
      if (n.text) {
        c.font = `12px ${col.sans}`;
        c.strokeText(n.text, tx, ty + 15);
        c.fillStyle = col.muted;
        c.fillText(n.text, tx, ty + 15);
      }
    }
    c.restore();
  }

  function buildTree() {
    const pts: number[] = [];
    for (let i = 0; i < keys.length; i++) if (alphas[i] > 0.15) pts.push(i);
    tree = quadtree<number>().x((i) => X(cur[2 * i])).y((i) => Y(cur[2 * i + 1])).addAll(pts);
  }

  function updateTip() {
    const i = shown ? index.get(shown) : undefined;
    tipPos = i === undefined ? null : { x: X(cur[2 * i]), y: Y(cur[2 * i + 1]) };
  }

  function pick(ev: MouseEvent, slop: number): string | null {
    if (!tree) return null;
    const rect = canvas.getBoundingClientRect();
    const i = tree.find(ev.clientX - rect.left, ev.clientY - rect.top, slop + 4);
    return i === undefined ? null : keys[i];
  }
  const maxR = () => radii.reduce((a, b) => Math.max(a, b), 0);

  function onMove(ev: PointerEvent) {
    if (ev.pointerType === 'touch') return;
    const key = pick(ev, maxR() + 2);
    if (key !== hovered) hovered = key;
    canvas.style.cursor = key ? 'pointer' : k > 1 ? 'grab' : 'default';
  }
  function onClick(ev: MouseEvent) {
    const key = pick(ev, lastPointer === 'touch' ? 18 : maxR() + 2);
    selected = key === selected ? null : key;
    if (lastPointer === 'touch') hovered = null;
  }
  function showHint(kind: 'wheel' | 'touch') {
    hint = kind === 'wheel' ? zoomHintText() : 'Use two fingers to zoom';
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => (hint = ''), 1500);
  }
  function onKey(ev: KeyboardEvent) {
    if (!zoomApi) return;
    const step = 60;
    const map: Record<string, () => void> = {
      '+': () => zoomApi!.zoomBy(1.6), '=': () => zoomApi!.zoomBy(1.6), '-': () => zoomApi!.zoomBy(1 / 1.6),
      '0': () => zoomApi!.reset(), ArrowLeft: () => zoomApi!.panBy(step / t.k, 0), ArrowRight: () => zoomApi!.panBy(-step / t.k, 0),
      ArrowUp: () => zoomApi!.panBy(0, step / t.k), ArrowDown: () => zoomApi!.panBy(0, -step / t.k),
      Escape: () => { selected = null; }
    };
    if (map[ev.key] && (k > 1 || !ev.key.startsWith('Arrow'))) { ev.preventDefault(); map[ev.key](); }
  }

  /** Views call this to frame part of the chart (coordinates in the layout's own units). */
  export function frameRect(x0: number, y0: number, x1: number, y1: number, animate = true) {
    zoomApi?.frame(x0 * s, y0 * s, x1 * s, y1 * s, animate);
  }
  export function resetZoom(animate = true) { zoomApi?.reset(animate); }

  let io: IntersectionObserver | null = null;
  onMount(() => {
    ctx = canvas.getContext('2d');
    col = {
      ink: token('--ink'), muted: token('--muted'), grid: token('--grid'), line: token('--line'), bg: token('--bg'),
      band: 'rgba(31, 30, 27, 0.028)', imdbInk: token('--imdb-ink'), lbInk: token('--lb-ink'), bothInk: token('--both-ink'),
      imdbEdge: token('--imdb-edge'), lbEdge: token('--lb-edge'), sans: token('--sans'), display: token('--display')
    };
    if (zoomable) {
      zoomApi = attachZoom(canvas, {
        maxZoom,
        onZoom: (tr) => { t = tr; k = tr.k; invalidate(); },
        onHint: showHint
      });
      zoomApi.resize(cw || 1, ch || 1);
    }
    // canvas text needs the web fonts: redraw once they are ready
    document.fonts?.ready.then(invalidate);
    if (intro === 'none') seen = true;
    if (!seen &&'IntersectionObserver' in window) {
      io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) { io?.disconnect(); playIntro(); }
      }, { threshold: 0.2 });
      io.observe(plotEl);
    } else if (!seen) playIntro();
    invalidate();
  });
  onDestroy(() => {
    zoomApi?.destroy();
    io?.disconnect();
    if (raf) cancelAnimationFrame(raf);
    clearTimeout(hintTimer);
  });

  const tipLeft = $derived(tipPos ? (tipPos.x > cw * 0.6 ? 'auto' : `${Math.max(4, tipPos.x + 14)}px`) : '0');
  const tipRight = $derived(tipPos ? (tipPos.x > cw * 0.6 ? `${Math.max(4, cw - tipPos.x + 14)}px` : 'auto') : 'auto');
  const tipTop = $derived(tipPos ? (tipPos.y > ch * 0.55 ? 'auto' : `${tipPos.y + 14}px`) : '0');
  const tipBottom = $derived(tipPos ? (tipPos.y > ch * 0.55 ? `${ch - tipPos.y + 14}px` : 'auto') : 'auto');
</script>

<!-- The figure is focusable so +, -, 0 and the arrow keys can zoom and pan. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
<figure class="chart" aria-label={ariaLabel} tabindex="0" onkeydown={onKey}>
  <div class="plot" bind:this={plotEl} bind:clientWidth={cw} style:height="{ch}px">
    <canvas
      bind:this={canvas}
      aria-hidden="true"
      onpointermove={onMove}
      onpointerleave={() => (hovered = null)}
      onpointerdown={(e) => (lastPointer = e.pointerType)}
      onclick={onClick}
    ></canvas>
    {#if hint}<div class="hint" role="status">{hint}</div>{/if}
    {#if tip && shown && tipPos}
      <div class="tip" class:pinned={selected === shown} style:left={tipLeft} style:right={tipRight} style:top={tipTop} style:bottom={tipBottom}>
        {@render tip(shown)}
        {#if selected === shown}
          <button type="button" class="close" aria-label="Close" onclick={() => (selected = null)}>×</button>
        {/if}
      </div>
    {/if}
  </div>
  {#if zoomable}
    <div class="foot">
      <span class="src">{source}</span>
      <span class="ctl">
        <span class="how">{k > 1.001 ? `${k.toFixed(1)}×` : zoomHintText()}</span>
        <button type="button" aria-label="Zoom out" disabled={k <= 1.001} onclick={() => zoomApi?.zoomBy(1 / 1.6)}>−</button>
        <button type="button" aria-label="Zoom in" onclick={() => zoomApi?.zoomBy(1.6)}>+</button>
        {#if k > 1.001}<button type="button" class="reset" onclick={() => zoomApi?.reset()}>Reset</button>{/if}
      </span>
    </div>
  {:else if source}
    <div class="foot"><span class="src">{source}</span></div>
  {/if}
  {#if children}<div class="sr-only">{@render children()}</div>{/if}
</figure>

<style>
  .chart { margin: 0; position: relative; border-radius: 6px; }
  .chart:focus-visible { box-shadow: var(--focus); }
  .plot { position: relative; width: 100%; transition: height 0.6s ease; }
  canvas { display: block; touch-action: pan-x pan-y; }
  .foot {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    margin-top: 6px; padding-top: 8px; border-top: 1px solid var(--grid); font: 12px var(--sans); color: var(--muted);
  }
  .how { font-variant-numeric: tabular-nums; margin-right: 6px; }
  .src { min-width: 0; }
  .ctl { display: inline-flex; gap: 4px; align-items: center; flex-shrink: 0; }
  @media (max-width: 600px) { .how { display: none; } }
  .ctl button {
    min-width: 30px; height: 28px; padding: 0 8px; border-radius: 99px; border: 1px solid var(--line);
    background: transparent; font-size: 14px; line-height: 1; cursor: pointer; color: var(--ink);
    transition: background 0.15s, border-color 0.15s;
  }
  .ctl button:hover:not(:disabled) { background: var(--surface); border-color: var(--muted); }
  .ctl button.reset { font-size: 12px; }
  .ctl button:disabled { opacity: 0.35; cursor: default; }
  .hint {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
    background: rgba(31, 30, 27, 0.84); color: var(--bg); font: 13px var(--sans); padding: 8px 14px; border-radius: 99px;
    pointer-events: none; white-space: nowrap;
  }
  .tip {
    position: absolute; z-index: 2; max-width: min(290px, 85%);
    background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 30px 10px 12px;
    font: 13px/1.4 var(--sans); box-shadow: 0 8px 28px rgba(31, 30, 27, 0.14); pointer-events: none;
  }
  .tip.pinned { pointer-events: auto; }
  .close {
    position: absolute; top: 4px; right: 6px; border: 0; background: none; font-size: 18px; line-height: 1;
    cursor: pointer; color: var(--muted); padding: 2px 4px;
  }
</style>

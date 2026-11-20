<!--
  The front page's film strip: all 500 entries drift from a scatter into two blocks, IMDb's 250 on the left and
  Letterboxd's 250 on the right, in rank order, coloured as everywhere else (grey = on both lists). Plays once on load;
  replay() runs it again (the page puts a Replay button under the title). Reduced motion: the dots are simply in place.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { token, prefersReducedMotion, type Film } from '$lib/data';
  let { films }: { films: Film[] } = $props();

  let wrap: HTMLDivElement, canvas: HTMLCanvasElement;
  let w = $state(0), h = $state(0);
  let raf = 0, start = 0;
  type Dot = { x0: number; y0: number; x1: number; y1: number; c: string; d: number };
  let dots: Dot[] = [];
  let r = 2;
  const DUR = 1500, SPREAD = 900;

  // a fixed pseudo-random scatter, so the start is the same on every visit
  const rand = (i: number) => { const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };

  function layout() {
    if (!w || !h || !films.length) return;
    const col = { imdb: token('--imdb'), lb: token('--lb'), both: token('--both') };
    const im = films.filter((f) => f.ir).sort((a, b) => a.ir! - b.ir!);
    const lb = films.filter((f) => f.lr && f.lr <= 250).sort((a, b) => a.lr! - b.lr!);
    const padY = 34, innerH = h - 2 * padY, sideW = w * 0.4;
    const cols = Math.ceil(Math.sqrt((250 * sideW) / innerH));
    const rows = Math.ceil(250 / cols);
    const step = Math.min(sideW / cols, innerH / rows);
    r = Math.max(1.2, step * 0.36);
    const blockW = (cols - 1) * step, blockH = (rows - 1) * step;
    const y0 = padY + (innerH - blockH) / 2;
    const place = (list: Film[], side: 'i' | 'l', x0: number) =>
      list.map((f, j): Dot => {
        const k = dots.length + j;
        return {
          x0: rand(k) * w, y0: padY + rand(k + 999) * innerH,
          x1: x0 + (j % cols) * step, y1: y0 + Math.floor(j / cols) * step,
          c: f.grp === 'both' ? col.both : side === 'i' ? col.imdb : col.lb,
          d: rand(k + 4242) * SPREAD
        };
      });
    dots = [];
    dots = [...place(im, 'i', w / 2 - 24 - blockW), ...place(lb, 'l', w / 2 + 24)];
  }

  const ease = (p: number) => 1 - Math.pow(1 - p, 3);
  function draw(now: number) {
    raf = 0;
    const c = canvas?.getContext('2d');
    if (!c || !w) return;
    const dpr = Math.min(2.5, window.devicePixelRatio || 1);
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const t = prefersReducedMotion() ? Infinity : now - start;
    let more = false;
    for (const d of dots) {
      const p = Math.max(0, Math.min(1, (t - d.d) / DUR));
      if (p < 1) more = true;
      const e = ease(p);
      c.globalAlpha = 0.35 + 0.65 * e;
      c.beginPath();
      c.arc(d.x0 + (d.x1 - d.x0) * e, d.y0 + (d.y1 - d.y0) * e, r, 0, Math.PI * 2);
      c.fillStyle = d.c;
      c.fill();
    }
    if (more) raf = requestAnimationFrame(draw);
  }
  export function replay() { start = performance.now(); if (!raf) raf = requestAnimationFrame(draw); }

  $effect(() => {
    void films;
    if (!canvas || !w || !h) return;
    const dpr = Math.min(2.5, window.devicePixelRatio || 1);
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    layout();
    if (!raf) raf = requestAnimationFrame(draw);
  });
  onMount(() => { start = performance.now(); });
  onDestroy(() => { if (raf) cancelAnimationFrame(raf); });
</script>

<div class="hero-dots" bind:this={wrap} bind:clientWidth={w} bind:clientHeight={h}>
  <canvas bind:this={canvas} style:width="{w}px" style:height="{h}px" aria-hidden="true"></canvas>
</div>

<style>
  .hero-dots { position: absolute; inset: 0; }
  canvas { display: block; }
</style>

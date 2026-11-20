// Geometric zoom for framed charts, with rules that never trap page scrolling:
//   - plain wheel scrolls the page (a hint says how to zoom); Ctrl/Cmd + wheel zooms (trackpad pinch sends Ctrl + wheel)
//   - one finger on a phone scrolls the page; two fingers pinch or pan the chart
//   - mouse drag pans, double-click zooms in (Shift + double-click zooms out), +/-/Reset buttons and keys always work
import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom';
import { select } from 'd3-selection';
import 'd3-transition';
import { prefersReducedMotion } from '$lib/data';

export interface ZoomApi {
  zoomBy(factor: number): void;
  panBy(dx: number, dy: number): void;
  reset(animate?: boolean): void;
  /** Frame a rectangle of the chart (in unzoomed screen pixels). Used by views. */
  frame(x0: number, y0: number, x1: number, y1: number, animate?: boolean): void;
  resize(w: number, h: number): void;
  destroy(): void;
}

export function attachZoom(
  el: Element,
  opts: { maxZoom: number; onZoom: (t: ZoomTransform) => void; onHint: (kind: 'wheel' | 'touch') => void }
): ZoomApi {
  let w = 1, h = 1;
  const behaviour = zoom<Element, unknown>()
    .scaleExtent([1, opts.maxZoom])
    .filter((e: any) => {
      if (e.type === 'wheel') {
        if (e.ctrlKey || e.metaKey) return true;
        opts.onHint('wheel');
        return false;
      }
      if (e.type === 'touchstart') return e.touches.length >= 2;
      if (e.type === 'mousedown') return e.button === 0;
      return !e.button;
    })
    .on('zoom', (e) => opts.onZoom(e.transform));
  const sel = select(el);
  sel.call(behaviour);
  // d3-zoom sets touch-action: none, which would stop one-finger page scrolling over the chart. Let the browser pan.
  (el as HTMLElement).style.touchAction = 'pan-x pan-y';

  const dur = (animate = true) => (animate && !prefersReducedMotion() ? 350 : 0);
  return {
    zoomBy(f) { sel.transition().duration(dur()).call(behaviour.scaleBy as any, f, [w / 2, h / 2]); },
    panBy(dx, dy) { sel.call(behaviour.translateBy as any, dx, dy); },
    reset(animate = true) { sel.transition().duration(dur(animate)).call(behaviour.transform as any, zoomIdentity); },
    frame(x0, y0, x1, y1, animate = true) {
      const k = Math.max(1, Math.min(opts.maxZoom, 0.9 / Math.max((x1 - x0) / w, (y1 - y0) / h)));
      const t = zoomIdentity.translate(w / 2, h / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
      sel.transition().duration(dur(animate) * 2).call(behaviour.transform as any, t);
    },
    resize(nw, nh) {
      w = nw; h = nh;
      behaviour.extent([[0, 0], [w, h]]).translateExtent([[0, 0], [w, h]]);
    },
    destroy() { sel.on('.zoom', null); }
  };
}

export const zoomHintText = () =>
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
    ? 'Hold ⌘ and scroll, or pinch, to zoom'
    : 'Hold Ctrl and scroll to zoom';

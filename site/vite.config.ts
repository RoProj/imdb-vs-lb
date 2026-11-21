import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => ({
  plugins: [sveltekit()],
  // the site's full address (set by the GitHub Pages workflow), so shared links can point at the preview image
  define: { __SITE_URL__: JSON.stringify((loadEnv(mode, '.', '').SITE_URL || '').replace(/\/$/, '')) },
  server: {
    port: 5188,
    strictPort: true,
    // production builds write here; watching them made the open page reload over and over after every build
    watch: { ignored: ['**/build/**', '**/.svelte-kit/output/**', '**/.svelte-kit-build/**'] }
  },
  // bundle the chart libraries up front, so the first visit to a page never triggers a "dependencies changed" reload
  optimizeDeps: {
    include: ['d3-quadtree', 'd3-zoom', 'd3-selection', 'd3-transition']
  }
}));

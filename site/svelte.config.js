import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    // 404.html: GitHub Pages shows it for any address the site doesn't have, and it renders src/routes/+error.svelte
    adapter: adapter({ fallback: '404.html' }),
    prerender: { entries: ['*'] },
    // GitHub Pages serves a project at /<repo-name>/; the deploy workflow sets BASE_PATH to that (empty everywhere else)
    paths: { base: process.env.BASE_PATH || '' },
    // production builds use their own working folder (set by `npm run build`), so building never rewrites the files
    // the running dev server uses, which made the open page reload several times per build
    outDir: process.env.SVELTEKIT_OUT || '.svelte-kit'
  }
};

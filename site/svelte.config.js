import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ fallback: undefined }),
    prerender: { entries: ['*'] },
    // production builds use their own working folder (set by `npm run build`), so building never rewrites the files
    // the running dev server uses, which made the open page reload several times per build
    outDir: process.env.SVELTEKIT_OUT || '.svelte-kit'
  }
};

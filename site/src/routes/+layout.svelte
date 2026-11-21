<script lang="ts">
  import { afterNavigate } from '$app/navigation';
  import { base } from '$app/paths';
  // following a link to another page always starts at the top of that page (never wherever the browser last was),
  // unless the link itself points somewhere on the page (#find, ?step=...)
  afterNavigate(({ type, to }) => {
    if (type !== 'link' && type !== 'goto') return;
    if (to?.url.hash || to?.url.searchParams.has('step')) return;
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  });
  import '@fontsource-variable/fraunces/opsz.css';
  import '@fontsource-variable/inter/opsz.css';
  import '../app.css';
  import { page } from '$app/state';
  let { children } = $props();

  // link previews (iMessage, WhatsApp, LinkedIn…) need full addresses; SITE_URL is set when building for GitHub Pages
  // (base can be a relative path like ".." while pages are pre-built, so the site's own path comes from SITE_URL)
  const site = __SITE_URL__;
  const sitePath = site ? new URL(site).pathname.replace(/\/$/, '') : '';
  const shareImage = site ? `${site}/og.png` : `${base}/og.png`;
  const pageUrl = $derived(site ? site + (page.url.pathname.startsWith(sitePath) ? page.url.pathname.slice(sitePath.length) : page.url.pathname) : '');
</script>

<svelte:head>
  <link rel="icon" href="{base}/favicon.svg" type="image/svg+xml" />
  <meta property="og:site_name" content="Quantifying Taste" />
  <meta property="og:image" content={shareImage} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="Quantifying Taste: IMDb’s and Letterboxd’s Top 250s drawn as dots side by side, with the films on both lists in grey." />
  <meta name="twitter:card" content="summary_large_image" />
  {#if pageUrl}<meta property="og:url" content={pageUrl} /><link rel="canonical" href={pageUrl} />{/if}
  <link rel="preload" href="{base}/data/films.json" as="fetch" crossorigin="anonymous" />
  <link rel="preload" href="{base}/data/numbers.json" as="fetch" crossorigin="anonymous" />
</svelte:head>

{@render children()}

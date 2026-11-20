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
  let { children } = $props();
</script>

<svelte:head>
  <link rel="icon" href="{base}/favicon.svg" type="image/svg+xml" />
  <link rel="preload" href="{base}/data/films.json" as="fetch" crossorigin="anonymous" />
  <link rel="preload" href="{base}/data/numbers.json" as="fetch" crossorigin="anonymous" />
</svelte:head>

{@render children()}

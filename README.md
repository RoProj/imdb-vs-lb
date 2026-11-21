# Quantifying Taste

**[View the live site →](https://roproj.github.io/imdb-vs-lb/)**

A scrolling data story comparing **IMDb's** Top 250 with the top 250 of **Letterboxd's** Top 500. Both sites let people rate the films they watch, and both keep a ranked list of the best. Only 111 films are on both. The story looks at where the two lists overlap and where they split: by country, by director, by how many films were directed by women, and by the films one list loves and the other leaves out. It ends with a short quiz: which list are you?

Built with SvelteKit and Svelte 5. The charts are drawn on canvas and driven by ordinary page scrolling. They work on phones, tablets and desktops, with keyboard support and a reduced-motion mode.

## Pages

1. **Two Top 250s.** The overlap, and how far apart shared films are ranked.
2. **Countries.** Where each list's films come from.
3. **Directors.** Who each list returns to most.
4. **Women directors.** How few films on either list were directed by women.
5. **Disagreements.** The films one list ranks high and the other doesn't include.
6. **Your turn.** Pick your favourites and see which list you lean toward.

## Data

- **The lists:** IMDb's Top 250, and the first 250 films of Letterboxd's official Top 500. Films ranked 251–500 on Letterboxd appear only on the last two pages. Both lists were read from the sites' public pages, since Letterboxd has no public API.
- **Country, director, year:** taken from IMDb for both lists, so a film is labelled the same way on each. One country per film: the first production country IMDb lists, with older names mapped to today's.
- **Directors' gender:** [Wikidata](https://www.wikidata.org/).

Collected on 13 November 2026. Both lists keep changing as people vote. The story says what these two lists suggest, not what all film fans think.

This is a personal, non-commercial project. It isn't affiliated with IMDb or Letterboxd.

© 2026 Rohan Projects · [@ro1projects](https://www.instagram.com/ro1projects/)

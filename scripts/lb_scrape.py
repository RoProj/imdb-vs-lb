"""Scrape Letterboxd's Top 500 list + each film page into data/letterboxd.csv.
Resumable: every fetched page is cached under raw/. Re-run to continue/parse only.
"""
import csv, html, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
FILMS = RAW / "lb_films"
FILMS.mkdir(parents=True, exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
LIST = "https://letterboxd.com/official/list/letterboxds-top-500-films/"
DELAY = 1.0


def get(url, tries=4):
    for i in range(tries):
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--http1.1", "-m", "40", "-A", UA, "-w", "\n%{http_code}", url],
            capture_output=True,
        )
        body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
        if r.returncode == 0 and code == "200" and "</html>" in body:
            return body
        print("  retry", url, r.returncode, code, r.stderr.decode()[:80], file=sys.stderr)
        time.sleep(3 * (i + 1))
    return None


def cached(path, url):
    if not path.exists():
        body = get(url)
        if body is None:
            return None
        path.write_text(body)
        time.sleep(DELAY)
    return path.read_text()


def uniq(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def parse_film(slug, s, rank):
    m = re.search(r'application/ld\+json">\s*/\*.*?\*/\s*(\{.*?\})\s*/\*', s, re.S)
    ld = json.loads(m.group(1)) if m else {}
    agg = ld.get("aggregateRating", {})
    year = None
    ev = ld.get("releasedEvent") or []
    if ev:
        year = ev[0].get("startDate")
    if not year:
        m = re.search(r'name="twitter:title" content="[^"]*\((\d{4})\)"', s)
        year = m.group(1) if m else None
    imdb = re.search(r'imdb\.com/title/(tt\d+)', s)
    tmdb = re.search(r'themoviedb\.org/movie/(\d+)', s)
    countries = uniq(re.findall(r'href="/films/country/([^"/]+)/"[^>]*>\s*([^<]+?)\s*<', s))
    langs = uniq(re.findall(r'href="/films/language/([^"/]+)/"[^>]*>\s*([^<]+?)\s*<', s))
    genres = uniq(re.findall(r'href="/films/genre/([^"/]+)/"[^>]*>\s*([^<]+?)\s*<', s))
    # Genres appear in the genres tab; 'themes'/'nanogenres' use other paths.
    directors = [d["name"] for d in ld.get("director", [])]
    return {
        "lb_rank": rank,
        "title": html.unescape(ld.get("name", slug)),
        "year": year,
        "directors": "; ".join(html.unescape(d) for d in directors),
        "genres": "; ".join(html.unescape(g[1]) for g in genres),
        "countries": "; ".join(html.unescape(c[1]) for c in countries),
        "primary_language": html.unescape(langs[0][1]) if langs else "",
        "languages": "; ".join(html.unescape(l[1]) for l in langs),
        "lb_rating": agg.get("ratingValue"),
        "lb_rating_count": agg.get("ratingCount"),
        "imdb_id": imdb.group(1) if imdb else "",
        "tmdb_id": tmdb.group(1) if tmdb else "",
        "lb_slug": slug,
    }


def main():
    slugs = []
    for p in range(1, 6):
        s = cached(RAW / f"lb_list_{p}.html", f"{LIST}page/{p}/")
        slugs += re.findall(r'data-item-slug="([^"]+)"', s)
    slugs = uniq(slugs)
    print(len(slugs), "films in list")
    rows = []
    for i, slug in enumerate(slugs, 1):
        s = cached(FILMS / f"{slug}.html", f"https://letterboxd.com/film/{slug}/")
        if s is None:
            print("FAILED", i, slug, flush=True)
            continue
        rows.append(parse_film(slug, s, i))
        if i % 25 == 0:
            print(i, "done", flush=True)
    with open(ROOT / "data" / "letterboxd.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", len(rows))


if __name__ == "__main__":
    main()

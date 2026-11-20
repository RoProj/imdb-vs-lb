"""Fetch Letterboxd rating + rating count for IMDb-Top-250 films that are not in Letterboxd's Top 500.
Uses letterboxd.com/imdb/<tt id>/ which redirects to the film page. Writes data/lb_extra.csv. Resumable."""
import csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lb_scrape as L

ROOT = L.ROOT
EXTRA = ROOT / "raw" / "lb_extra"
EXTRA.mkdir(exist_ok=True)

imdb = [r["imdb_id"] for r in csv.DictReader(open(ROOT / "data" / "imdb_top250.csv", encoding="utf-8"))]
lb = {r["imdb_id"] for r in csv.DictReader(open(ROOT / "data" / "letterboxd.csv", encoding="utf-8")) if r["imdb_id"]}
need = [i for i in imdb if i not in lb]
print(len(need), "films to fetch", flush=True)
rows = []
for n, i in enumerate(need, 1):
    s = L.cached(EXTRA / f"{i}.html", f"https://letterboxd.com/imdb/{i}/")
    if s is None:
        rows.append({"imdb_id": i, "lb_slug": "", "lb_rating": "", "lb_rating_count": "", "status": "fetch_failed"})
        continue
    r = L.parse_film(i, s, 0)
    ok = bool(r["lb_rating"]) and r["imdb_id"] in ("", i)
    rows.append({"imdb_id": i, "lb_slug": r["lb_slug"], "lb_rating": r["lb_rating"] or "",
                 "lb_rating_count": r["lb_rating_count"] or "", "status": "ok" if ok else "check",
                 "lb_title": r["title"], "lb_year": r["year"]})
    if n % 20 == 0:
        print(n, "done", flush=True)
cols = ["imdb_id", "lb_slug", "lb_rating", "lb_rating_count", "status", "lb_title", "lb_year"]
with open(ROOT / "data" / "lb_extra.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print("wrote", len(rows), "| ok:", sum(r["status"] == "ok" for r in rows))

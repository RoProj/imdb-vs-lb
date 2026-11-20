"""Build data/viz_films.csv: one row per film per list (500 rows) carrying BOTH sites' numbers for each film.
Run after unify.py / make_250.py / lb_extra.py."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8", newline="")))

uni = rd(D / "unified.csv")                      # includes LB ranks 251-500
cmp250 = rd(D / "comparison_250.csv")
imdb250 = {r["imdb_id"]: r for r in rd(D / "imdb_top250.csv")}
imdb_meta = {r["imdb_id"]: r for r in rd(ROOT / "raw" / "imdb_meta_for_lb_raw.csv")}
extra = {r["imdb_id"]: r for r in rd(D / "lb_extra.csv") if r["status"] == "ok"}
lb500 = {r["imdb_id"]: r for r in uni if r["list"] == "LB500"}

def imdb_stats(i):
    if i in imdb250:
        r = imdb250[i]; return r["title"], r["imdb_rating"], r["imdb_votes"]
    r = imdb_meta[i]; return r["title"], r["imdb_rating"], r["imdb_votes"]

def lb_stats(i):
    if i in lb500:
        r = lb500[i]; return r["rating_native"], r["rating_count"], r["rank"]
    if i in extra:
        r = extra[i]; return r["lb_rating"], r["lb_rating_count"], ""
    return "", "", ""

out, miss = [], []
for r in cmp250:
    i = r["imdb_id"]
    title, ir, iv = imdb_stats(i)
    lr, lc, l500 = lb_stats(i)
    rank_imdb = imdb250[i]["imdb_rank"] if i in imdb250 else ""
    rank_lb250 = l500 if l500 and int(l500) <= 250 else ""
    if not lr: miss.append(title)
    out.append({
        "list": r["list"], "rank": r["rank"], "imdb_id": i, "title": title, "year": r["year"], "decade": r["decade"],
        "directors": r["directors"], "genres": r["genres"], "country": r["country"], "countries": r["countries"],
        "primary_language": r["primary_language"], "is_silent": r["is_silent"],
        "imdb_rank": rank_imdb, "lb_rank250": rank_lb250, "lb_rank500": l500,
        "imdb_rating": ir, "imdb_votes": iv, "lb_rating": lr, "lb_rating_10": f"{float(lr)*2:.2f}" if lr else "",
        "lb_count": lc, "director_country": r.get("director_country", ""),
    })
cols = list(out[0])
with open(D / "viz_films.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
print("rows", len(out), "| distinct films", len({r['imdb_id'] for r in out}), "| missing LB rating:", miss)
for c in ["title", "year", "genres", "country", "primary_language", "imdb_rating", "imdb_votes", "lb_rating", "lb_count"]:
    print(f"empty {c}: {sum(1 for r in out if not str(r[c]).strip())}")
both = {r['imdb_id'] for r in out if r['list']=='IMDb250'} & {r['imdb_id'] for r in out if r['list']=='LB250'}
print("on both top-250 lists:", len(both), "| IMDb250 films with LB rank in 251-500:",
      sum(1 for r in out if r['list']=='IMDb250' and r['lb_rank500'] and int(r['lb_rank500'])>250))

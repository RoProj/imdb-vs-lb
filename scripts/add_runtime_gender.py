"""Add runtime and director gender columns to data/viz_films.csv (idempotent; run after build_films.py).

Runtime : minutes, parsed from each film's cached Letterboxd page (raw/runtime_from_lb_pages.json) so both lists use one source.
Gender  : as recorded on Wikidata (property P21, "sex or gender") for every director Wikidata lists for the film
          (raw/wikidata_director_gender.json). Not self-reported by us and not inferred from names.
          "women" = Wikidata gender of female or trans woman; shown separately in director_genders.
New columns:
  runtime_min, directors_wd (number of directors Wikidata lists), directors_women, directors_men,
  has_woman_director (1/0), director_genders (e.g. "male; female"), gender_check (ok / count_differs / unknown_gender)
"""
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
runtime = json.load(open(ROOT / "raw" / "runtime_from_lb_pages.json"))
WOMEN = {"female", "trans woman"}
MEN = {"male", "trans man"}

dirs = defaultdict(dict)  # imdb_id -> {director qid: gender label or ""}
for b in json.load(open(ROOT / "raw" / "wikidata_director_gender.json", encoding="utf-8")):
    dirs[b["imdb"]][b["dir"]] = b.get("gLabel", "")

rows = list(csv.DictReader(open(D / "viz_films.csv", encoding="utf-8", newline="")))
new = ["runtime_min", "directors_wd", "directors_women", "directors_men", "has_woman_director", "director_genders", "gender_check"]
fields = [f for f in rows[0] if f not in new] + new
for r in rows:
    i = r["imdb_id"]
    g = list(dirs.get(i, {}).values())
    n_imdb = len([d for d in r["directors"].split(";") if d.strip()])
    r["runtime_min"] = runtime.get(i, "")
    r["directors_wd"] = len(g)
    r["directors_women"] = sum(x in WOMEN for x in g)
    r["directors_men"] = sum(x in MEN for x in g)
    r["has_woman_director"] = int(r["directors_women"] > 0)
    r["director_genders"] = "; ".join(g)
    unknown = any(x not in WOMEN | MEN for x in g)
    r["gender_check"] = "unknown_gender" if unknown or not g else ("count_differs" if len(g) != n_imdb else "ok")
with open(D / "viz_films.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

from collections import Counter
u = {r["imdb_id"]: r for r in rows}
print("films", len(u), "| gender_check:", Counter(r["gender_check"] for r in u.values()))
print("gender labels:", Counter(x for r in u.values() for x in r["director_genders"].split("; ") if x))
for k, v in (("IMDb250", [r for r in rows if r["list"] == "IMDb250"]), ("LB250", [r for r in rows if r["list"] == "LB250"])):
    w = sum(int(r["has_woman_director"]) for r in v)
    cw = sum(int(r["directors_women"]) for r in v); cm = sum(int(r["directors_men"]) for r in v)
    print(f"{k}: films with a woman director {w}/250 ({w/250*100:.1f}%) | director credits women {cw}, men {cm} ({cw/(cw+cm)*100:.1f}% women)")

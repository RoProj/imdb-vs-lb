"""Add ONE 'main' production country per film to data/unified.csv.

Rule (two independent sources must back the answer):
  1. Wikidata 'country of origin' (P495) has exactly one value  -> use it        (source = wikidata)
  2. Wikidata has several values -> first country in IMDb's order that Wikidata
     also lists                                                 -> use it        (source = wikidata+imdb)
  3. No overlap between the two                                  -> IMDb first    (source = imdb_only, review)
Run after unify.py (unify.py rebuilds unified.csv without these columns).
Wikidata results: raw/wikidata_country_origin.json  {imdb_id: [country labels]}
"""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
WD = json.load(open(ROOT / "raw" / "wikidata_country_origin.json", encoding="utf-8"))

WD_LABEL = {"Weimar Republic": "Germany", "Kingdom of Italy": "Italy",
            "People's Republic of China": "China",
            "Federal Republic of Yugoslavia": "Yugoslavia", "The Gambia": "Gambia"}
MODERN = {"West Germany": "Germany", "Soviet Union": "Russia", "Czechoslovakia": "Czech Republic",
          "Yugoslavia": "Serbia"}
# Manual overrides after review: imdb_id -> country (title kept for readability)
# Deliberately empty: the rule must apply uniformly to every film, with no hand-picked exceptions.
OVERRIDE = {}

rows = list(csv.DictReader(open(D / "unified.csv", encoding="utf-8", newline="")))
fields = [f for f in rows[0] if f not in ("country_main", "country_main_modern", "country_main_source", "wikidata_countries")]
for r in rows:
    imdb = [c for c in r["countries"].split("; ") if c]
    wd = [WD_LABEL.get(c, c) for c in WD.get(r["imdb_id"], [])]
    if r["imdb_id"] in OVERRIDE:
        main, src = OVERRIDE[r["imdb_id"]], "manual"
    elif len(wd) == 1:
        main, src = wd[0], "wikidata"
    else:
        wd_modern = {MODERN.get(c, c) for c in wd}
        hit = next((c for c in imdb if MODERN.get(c, c) in wd_modern), None)  # compare modern names ("West Germany" == "Germany")
        main, src = (hit, "wikidata+imdb") if hit else (imdb[0], "imdb_only")
    r["country_main"] = main
    r["country_main_modern"] = MODERN.get(main, main)
    r["country_main_source"] = src
    r["wikidata_countries"] = "; ".join(wd)

with open(D / "unified.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields + ["country_main", "country_main_modern", "country_main_source", "wikidata_countries"])
    w.writeheader()
    w.writerows(rows)

films = {r["imdb_id"]: r for r in rows}
src = {}
for r in films.values():
    src[r["country_main_source"]] = src.get(r["country_main_source"], 0) + 1
changed = [r for r in films.values() if r["country_main"] != r["countries"].split("; ")[0]
           and r["country_main_modern"] != r["countries"].split("; ")[0]]
print("films:", len(films), "| by source:", src)
print("main country differs from IMDb first-listed:", len(changed))
for r in changed:
    print("  ", r["title"], "|", r["country_main"], "| IMDb:", r["countries"].split("; ")[:3], "| WD:", r["wikidata_countries"], "|", r["country_main_source"])
print("\nimdb_only (no agreement between sources):")
for r in films.values():
    if r["country_main_source"] == "imdb_only":
        print("  ", r["title"], "| IMDb:", r["countries"].split("; ")[:3], "| WD:", r["wikidata_countries"])

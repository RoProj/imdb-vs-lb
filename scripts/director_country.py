"""Add director nationality to data/comparison_250.csv (run after make_250.py).

Rule, applied identically to every film (no manual overrides):
  director  = the film's first-listed director (IMDb order), matched to Wikidata by name;
              if the name can't be matched but Wikidata has exactly one director for the film, use that one.
  country   = 1. Wikidata citizenship, historical states mapped to today's country; if exactly one -> use it
              2. several citizenships -> the director's country of birth, if it is one of them
              3. otherwise the first citizenship listed (flagged: director_country_source = citizenship_first)
              4. no citizenship on Wikidata -> country of birth (source = birth), else blank
"""
import csv, json, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
HIST = {"Empire of Japan": "Japan", "Kingdom of Italy": "Italy", "Cisleithania": "Austria",
        "United Kingdom of Great Britain and Ireland": "United Kingdom", "Kingdom of the Netherlands": "Netherlands",
        "Soviet Union": "Russia", "Czechoslovakia": "Czech Republic", "West Germany": "Germany",
        "Socialist Federal Republic of Yugoslavia": "Serbia", "Federal Republic of Yugoslavia": "Serbia",
        "Yugoslavia": "Serbia", "People's Republic of China": "China", "Qajar Iran": "Iran", "Pahlavi Iran": "Iran",
        "Weimar Republic": "Germany", "Nazi Germany": "Germany", "Russian Empire": "Russia",
        "Austria-Hungary": "Austria", "Kingdom of Hungary": "Hungary", "Second Polish Republic": "Poland"}
fold = lambda s: "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if c.isalnum())
mp = lambda xs: list(dict.fromkeys(HIST.get(x, x) for x in xs))

films = defaultdict(dict)
for b in json.load(open(ROOT / "raw" / "wikidata_directors.json", encoding="utf-8")):
    d = films[b["imdb"]].setdefault(b["dir"], {"name": b.get("dirLabel", ""), "cit": [], "birth": []})
    if "cLabel" in b and b["cLabel"] not in d["cit"]:
        d["cit"].append(b["cLabel"])
    if "bLabel" in b and b["bLabel"] not in d["birth"]:
        d["birth"].append(b["bLabel"])

rows = list(csv.DictReader(open(D / "comparison_250.csv", encoding="utf-8", newline="")))
fields = [f for f in rows[0] if not f.startswith("director_country") and f != "director_wikidata_match"]
cache = {}
for r in rows:
    i = r["imdb_id"]
    if i in cache:
        r.update(cache[i]); continue
    dirs = list(films.get(i, {}).values())
    hit = [d for d in dirs if fold(d["name"]) == fold(r["director_primary"])]
    match = "name"
    if not hit and len(dirs) == 1:
        hit, match = dirs, "sole"
    res = {"director_country": "", "director_country_source": "unknown", "director_wikidata_match": "none"}
    if hit:
        d = hit[0]; cit, birth = mp(d["cit"]), mp(d["birth"])
        res["director_wikidata_match"] = match
        if len(cit) == 1:
            res.update(director_country=cit[0], director_country_source="citizenship")
        elif len(cit) > 1:
            b = next((x for x in birth if x in cit), None)
            if b: res.update(director_country=b, director_country_source="citizenship+birth")
            else: res.update(director_country=cit[0], director_country_source="citizenship_first")
        elif birth:
            res.update(director_country=birth[0], director_country_source="birth")
    cache[i] = res; r.update(res)

with open(D / "comparison_250.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields + ["director_country", "director_country_source", "director_wikidata_match"])
    w.writeheader(); w.writerows(rows)

from collections import Counter
u = {r["imdb_id"]: r for r in rows}
print("distinct films:", len(u), Counter(r["director_country_source"] for r in u.values()))
print("matched by:", Counter(r["director_wikidata_match"] for r in u.values()))
for k in ("citizenship_first", "unknown"):
    print(f"\n{k}:"); [print("  ", r["title"], "|", r["director_primary"], "->", r["director_country"] or "?") for r in u.values() if r["director_country_source"] == k]
for nm in ("IMDb250", "LB250"):
    sub = [r for r in rows if r["list"] == nm]; c = Counter(r["director_country"] for r in sub)
    print(nm, ", ".join(f"{k or '?'} {v} ({v/len(sub):.0%})" for k, v in c.most_common(7)))

"""Build one comparable dataset: IMDb Top 250 + Letterboxd Top 500.

Country / language / genre / director / year come from ONE source (IMDb) for BOTH lists,
so the two lists cannot disagree because of labelling. Each site keeps its OWN rank and rating.
Letterboxd's own labels are kept in lb_* columns for reference only.

Inputs : data/imdb_top250.csv, raw/imdb_meta_for_lb_raw.csv, data/letterboxd.csv
Output : data/unified.csv (one row per film per list), data/overlap.csv, data/mappings/*.csv
Edit the mapping dicts and re-run -- no re-scraping needed.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
(D / "mappings").mkdir(exist_ok=True)

# ---- mappings (IMDb labels -> tidy labels) ----------------------------------
COUNTRY = {"Federal Republic of Yugoslavia": "Yugoslavia",
           "Occupied Palestinian Territory": "Palestine"}
# JUDGEMENT CALL: successor states for historical countries (countries_modern column).
COUNTRY_MODERN = {"West Germany": "Germany", "Soviet Union": "Russia",
                  "Czechoslovakia": "Czech Republic", "Yugoslavia": "Serbia"}
LANGUAGE = {"Romany": "Romani", "Slovenian": "Slovene",
            "Greek, Ancient (to 1453)": "Ancient Greek", "Irish Gaelic": "Irish",
            "Saami": "Sami", "Hokkien": "Min Nan"}
# NOT merged: Mandarin vs Chinese, Gaelic (ambiguous), Filipino vs Tagalog.
DIRECTOR = {"Charles Chaplin": "Charlie Chaplin"}


def split(s):
    return [x.strip() for x in (s or "").split(";") if x.strip()]


def mapped(vals, table):
    out = []
    for v in vals:
        v = table.get(v, v)
        if v not in out:
            out.append(v)
    return out


def read(p):
    return list(csv.DictReader(open(p, encoding="utf-8", newline="")))


# ---- IMDb metadata for every film we need ----------------------------------
meta = {}
for r in read(D / "imdb_top250.csv"):
    meta[r["imdb_id"]] = {"directors": r["directors"], "genres": r["genres"], "countries": r["countries"],
                          "languages": r["languages"], "silent": r["is_silent"] == "1", "year": r["year"],
                          "title": r["title"], "imdb_rating": r["imdb_rating"], "imdb_votes": r["imdb_votes"]}
for r in read(ROOT / "raw" / "imdb_meta_for_lb_raw.csv"):
    langs = split(r["languages"])
    meta[r["imdb_id"]] = {"directors": r["directors"], "genres": r["genres"], "countries": r["countries"],
                          "languages": "; ".join(l for l in langs if l != "None"), "silent": "None" in langs,
                          "year": r["year"], "title": r["title"], "imdb_rating": r["imdb_rating"],
                          "imdb_votes": r["imdb_votes"]}

# Letterboxd lists Gangs of Wasseypur Part 2 separately; IMDb has it as one film (tt1954470).
ASSUMED = {"gangs-of-wasseypur-part-2": "tt1954470"}


def build(m):
    countries = mapped(split(m["countries"]), COUNTRY)
    langs = mapped(split(m["languages"]), LANGUAGE)
    directors = mapped(split(m["directors"]), DIRECTOR)
    return {
        "directors": "; ".join(directors),
        "director_primary": directors[0] if directors else "",
        "genres": "; ".join(split(m["genres"])),
        "countries": "; ".join(countries),
        "countries_modern": "; ".join(mapped(countries, COUNTRY_MODERN)),
        "n_countries": len(countries),
        "primary_language": "Silent" if m["silent"] else (langs[0] if langs else ""),
        "languages": "; ".join(langs),
        "is_silent": int(m["silent"]),
        "year": m["year"],
        "decade": f"{int(m['year']) // 10 * 10}s",
    }


rows = []
for r in read(D / "imdb_top250.csv"):
    row = {"list": "IMDb250", "rank": r["imdb_rank"], "imdb_id": r["imdb_id"], "title": r["title"],
           "rating_native": r["imdb_rating"], "rating_scale": 10, "rating_10": r["imdb_rating"],
           "rating_count": r["imdb_votes"], "imdb_id_assumed": 0, "lb_slug": "",
           "lb_countries": "", "lb_languages": "", "lb_genres": "", "lb_directors": ""}
    row.update(build(meta[r["imdb_id"]]))
    rows.append(row)

missing = []
for r in read(D / "letterboxd.csv"):
    iid, assumed = r["imdb_id"], 0
    if not iid and r["lb_slug"] in ASSUMED:
        iid, assumed = ASSUMED[r["lb_slug"]], 1
    if iid not in meta:
        missing.append((r["lb_rank"], r["title"]))
        continue
    row = {"list": "LB500", "rank": r["lb_rank"], "imdb_id": iid, "title": r["title"],
           "rating_native": r["lb_rating"], "rating_scale": 5,
           "rating_10": f"{float(r['lb_rating']) * 2:.2f}", "rating_count": r["lb_rating_count"],
           "imdb_id_assumed": assumed, "lb_slug": r["lb_slug"], "lb_countries": r["countries"],
           "lb_languages": r["languages"], "lb_genres": r["genres"], "lb_directors": r["directors"]}
    row.update(build(meta[iid]))
    rows.append(row)

cols = ["list", "rank", "imdb_id", "title", "year", "decade", "directors", "director_primary", "genres",
        "countries", "countries_modern", "n_countries", "primary_language", "languages", "is_silent",
        "rating_native", "rating_scale", "rating_10", "rating_count", "imdb_id_assumed", "lb_slug",
        "lb_countries", "lb_languages", "lb_genres", "lb_directors"]
with open(D / "unified.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

# ---- overlap ----------------------------------------------------------------
im = {r["imdb_id"]: r for r in rows if r["list"] == "IMDb250"}
lb = {}
for r in rows:
    if r["list"] == "LB500":
        lb.setdefault(r["imdb_id"], r)
ov = []
for k, a in sorted(im.items(), key=lambda kv: int(kv[1]["rank"])):
    b = lb.get(k)
    ov.append({"imdb_id": k, "title": a["title"], "year": a["year"], "imdb_rank": a["rank"],
               "lb_rank": b["rank"] if b else "", "in_lb500": int(bool(b)),
               "in_lb250": int(bool(b) and int(b["rank"]) <= 250),
               "imdb_rating": a["rating_10"], "lb_rating_10": b["rating_10"] if b else ""})
with open(D / "overlap.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(ov[0]))
    w.writeheader()
    w.writerows(ov)

for name, table in (("country", COUNTRY), ("country_modern", COUNTRY_MODERN), ("language", LANGUAGE),
                    ("director", DIRECTOR)):
    with open(D / "mappings" / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["raw", "normalised"])
        w.writerows(table.items())

# ---- checks -----------------------------------------------------------------
n_im = sum(r["list"] == "IMDb250" for r in rows)
n_lb = sum(r["list"] == "LB500" for r in rows)
print(f"rows: IMDb250={n_im}  LB500={n_lb}  unresolved={missing}")
for col in ["year", "directors", "genres", "countries", "primary_language", "rating_10"]:
    bad = [(r["list"], r["rank"], r["title"]) for r in rows if not str(r[col]).strip()]
    print(f"empty {col:17s}: {bad[:5]} ({len(bad)})")
dups = {}
for r in rows:
    if r["list"] == "LB500":
        dups.setdefault(r["imdb_id"], []).append(r["title"])
print("LB films sharing an IMDb ID:", {k: v for k, v in dups.items() if len(v) > 1})
print(f"overlap: IMDb250 in LB500={sum(o['in_lb500'] for o in ov)}  in LB250={sum(o['in_lb250'] for o in ov)}")
# how much did Letterboxd's own labels disagree with the IMDb source? (informational)
lbr = [r for r in rows if r["list"] == "LB500" and r["lb_countries"]]
print("LB own-country label differs from IMDb-sourced set (incl. spelling):",
      sum(set(split(r["lb_countries"])) != set(split(r["countries"])) for r in lbr), "of", len(lbr))

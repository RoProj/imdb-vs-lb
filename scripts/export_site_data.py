"""Export the two files the website ships: data/site/films.json and data/site/numbers.json.

Run:   python3 -I scripts/export_site_data.py
Then:  python3 -I scripts/check_export.py      (the gate: must pass before the site is built or published)

films.json   one record per film (579): the 389 films on either top 250, plus the 190 films that are only in
             Letterboxd's ranks 251 to 500 (used by search and the quiz, never drawn in the story charts).
numbers.json every number the page prints, under a stable key, plus the small series the bar charts draw.
             The page inserts numbers by key and never types them.

Field rules are the project's decided ones: country, language, genre, director and year come from IMDb for every film;
country is IMDb's first-listed production country with historical names mapped to modern ones; each site keeps its own
rank and rating, and Letterboxd ratings are doubled to a 10-point scale.
"""
import csv, json, math, statistics as st
from math import comb
from pathlib import Path
import re as _re, unicodedata as _ud
def dslug(name):
    """number-key slug for a director: 'Hirokazu Koreeda' -> 'hirokazu_koreeda'"""
    return _re.sub(r"[^a-z0-9]+", "_", _ud.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("_")

ROOT = Path(__file__).resolve().parent.parent
D, RAW, OUT = ROOT / "data", ROOT / "raw", ROOT / "data" / "site"
COLLECTED = "2026-11-13"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8", newline="")))
split = lambda s: [x.strip() for x in s.split(";") if x.strip()]
num = lambda s, f=int: f(s) if str(s).strip() != "" else None

# ------------------------------------------------------------------ load
viz = rd(D / "viz_films.csv")
uni = rd(D / "unified.csv")
gcred = {r["imdb_id"]: r for r in rd(D / "gender_credits.csv")}
meta = {r["imdb_id"]: r for r in rd(RAW / "imdb_meta_for_lb_raw.csv")}
lb500 = {r["imdb_id"]: r for r in uni if r["list"] == "LB500"}
IM, LB = "IMDb250", "LB250"
rows = {k: [r for r in viz if r["list"] == k] for k in (IM, LB)}
ids = {k: {r["imdb_id"] for r in v} for k, v in rows.items()}
distinct = {}
for r in viz:
    distinct.setdefault(r["imdb_id"], r)


def group(i):
    a, b = i in ids[IM], i in ids[LB]
    return "both" if a and b else "imdb" if a else "lb" if b else "lb500"


def women_director_names(r):
    if r["has_woman_director"] != "1":
        return None
    names, genders = split(r["directors"]), split(r["director_genders"])
    if len(names) != len(genders):
        raise SystemExit(f"cannot match director genders for {r['title']}")
    return [n for n, g in zip(names, genders) if g in ("female", "trans woman")]


# ------------------------------------------------------------------ films.json
films = []
for i, r in distinct.items():
    g = gcred.get(i, {})
    lead = g.get("lead_is_woman", "")
    aka = lb500[i]["title"] if i in lb500 and lb500[i]["title"] != r["title"] else None
    films.append({
        "id": i, "t": r["title"], "aka": [aka] if aka else None, "y": int(r["year"]), "rt": num(r["runtime_min"]),
        "d": split(r["directors"]), "g": split(r["genres"]), "c": r["country"], "cs": split(r["countries"]),
        "l": r["primary_language"], "s": int(r["is_silent"]),
        "ir": num(r["imdb_rank"]), "lr": num(r["lb_rank500"]),
        "iR": float(r["imdb_rating"]), "iv": int(r["imdb_votes"]),
        "lR": float(r["lb_rating_10"]), "lv": num(r["lb_count"]),
        "grp": group(i),
        "wd": int(r["has_woman_director"]), "wdn": women_director_names(r),
        "lw": int(lead) if lead != "" else None,
        "t3w": num(g.get("top3_women", "")), "t3n": num(g.get("top3_n", "")),
    })

for i, r in lb500.items():
    if i in distinct:
        continue
    m = meta[i]  # IMDb's own metadata for Letterboxd-only films (title, rating, votes)
    cs = split(r["countries_modern"])
    films.append({
        "id": i, "t": m["title"], "aka": [r["title"]] if r["title"] != m["title"] else None, "y": int(r["year"]),
        "rt": None, "d": split(r["directors"]), "g": split(r["genres"]), "c": cs[0], "cs": split(r["countries"]),
        "l": r["primary_language"], "s": int(r["is_silent"]),
        "ir": None, "lr": int(r["rank"]),
        "iR": num(m["imdb_rating"], float), "iv": num(m["imdb_votes"]),
        "lR": float(r["rating_10"]), "lv": num(r["rating_count"]),
        "grp": "lb500",
    })

films.sort(key=lambda f: (f["ir"] or 999, f["lr"] or 999))
films = [{k: v for k, v in f.items() if v is not None} for f in films]

# ------------------------------------------------------------------ numbers.json helpers
N, S = {}, {}
pct = lambda n, d: int(n / d * 100 + 0.5)              # whole percent, half rounds up (same rule as check_numbers.py)
pct1 = lambda n, d: math.floor(n / d * 1000 + 0.5) / 10  # one decimal, half rounds up


def put(key, n, d=None, one_decimal=False):
    """Store a count; with a denominator also store the share."""
    N[key + ".n" if d else key] = n
    if d:
        N[key + ".of"] = d
        N[key + ".pct"] = pct1(n, d) if one_decimal else pct(n, d)


def pair(key, f, d=None, one_decimal=False):
    for side, k in (("imdb", IM), ("lb", LB)):
        put(f"{key}.{side}", f(k), d(k) if callable(d) else d, one_decimal)


def fisher(a, n1, b, n2):
    k, n = a + b, n1 + n2
    p = lambda x: comb(n1, x) * comb(n2, k - x) / comb(n, k)
    p0 = p(a)
    return sum(p(x) for x in range(max(0, k - n2), min(n1, k) + 1) if p(x) <= p0 * (1 + 1e-9))


def wilson(k, n, z=1.959964):
    p, dn = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / dn, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / dn
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def tally(k, f):
    out = {}
    for r in rows[k]:
        for v in f(r):
            out[v] = out.get(v, 0) + 1
    return out


def series(f, sort="total"):
    a, b = tally(IM, f), tally(LB, f)
    out = [{"name": n, "imdb": a.get(n, 0), "lb": b.get(n, 0),
            "imdb_pct": pct(a.get(n, 0), 250), "lb_pct": pct(b.get(n, 0), 250),
            "gap_pp": round((b.get(n, 0) - a.get(n, 0)) * 100 / 250, 1)} for n in set(a) | set(b)]
    key = (lambda x: (-(x["imdb"] + x["lb"]), x["name"])) if sort == "total" else (lambda x: x["name"])
    return sorted(out, key=key)


# ------------------------------------------------------------------ overlap
both = ids[IM] & ids[LB]
N["lists.size"] = 250
N["overlap.both"] = len(both)
N["overlap.imdb_only"] = len(ids[IM] - ids[LB])
N["overlap.lb_only"] = len(ids[LB] - ids[IM])
N["overlap.distinct"] = len(distinct)
N["overlap.imdb_only.lb251_500"] = sum(1 for r in rows[IM] if r["lb_rank500"] and int(r["lb_rank500"]) > 250)
N["overlap.imdb_only.not_in_lb500"] = sum(1 for r in rows[IM] if not r["lb_rank500"])
N["search.films"] = len(films)
N["search.lb251_500_only"] = sum(1 for f in films if f["grp"] == "lb500")

# ------------------------------------------------------------------ country
S["country"] = series(lambda r: [r["country"]])
for name, key in [("United States", "us"), ("Japan", "japan"), ("United Kingdom", "uk"), ("France", "france"), ("Italy", "italy"),
                  ("India", "india"), ("Germany", "germany"), ("Russia", "russia"), ("Iran", "iran"), ("Sweden", "sweden"), ("South Korea", "korea")]:
    pair(f"country.{key}", lambda k: sum(1 for r in rows[k] if r["country"] == name), 250)
LEAN = {"United States", "Japan", "United Kingdom", "Italy", "France", "India", "Germany", "Russia", "Iran", "Sweden", "South Korea"}
pair("country.rest", lambda k: sum(1 for r in rows[k] if r["country"] not in LEAN), 250)
pair("country.count", lambda k: len({r["country"] for r in rows[k]}))
pair("country.top3", lambda k: sum(sorted(tally(k, lambda r: [r["country"]]).values(), reverse=True)[:3]), 250)
pair("country.coproduction", lambda k: sum(1 for r in rows[k] if len(split(r["countries"])) > 1), 250)

# ------------------------------------------------------------------ year
yrs = {k: [int(r["year"]) for r in rows[k]] for k in rows}
pair("year.median", lambda k: st.median(yrs[k]))
pair("year.mean", lambda k: round(st.mean(yrs[k]), 1))
pair("year.since2000", lambda k: sum(y >= 2000 for y in yrs[k]), 250)
pair("year.before1970", lambda k: sum(y < 1970 for y in yrs[k]), 250)
pair("year.earliest", lambda k: min(yrs[k]))
pair("year.latest", lambda k: max(yrs[k]))
decades = range((min(min(v) for v in yrs.values()) // 10) * 10, max(max(v) for v in yrs.values()) + 1, 10)
S["decade"] = [{"name": f"{d}s", "imdb": sum(d <= y < d + 10 for y in yrs[IM]), "lb": sum(d <= y < d + 10 for y in yrs[LB])} for d in decades]
for d in S["decade"]:
    N[f"decade.{d['name']}.imdb"], N[f"decade.{d['name']}.lb"] = d["imdb"], d["lb"]

# ------------------------------------------------------------------ runtime
rt = {k: [int(r["runtime_min"]) for r in rows[k]] for k in rows}
pair("runtime.median", lambda k: st.median(rt[k]))
pair("runtime.mean", lambda k: round(st.mean(rt[k])))
pair("runtime.2h_plus", lambda k: sum(x >= 120 for x in rt[k]), 250)
pair("runtime.3h_plus", lambda k: sum(x >= 180 for x in rt[k]))
pair("runtime.under90", lambda k: sum(x < 90 for x in rt[k]))
by_rt = sorted(distinct.values(), key=lambda r: (-int(r["runtime_min"]), r["title"]))
S["runtime_longest"] = [{"id": r["imdb_id"], "t": r["title"], "rt": int(r["runtime_min"]), "grp": group(r["imdb_id"])} for r in by_rt[:5]]
S["runtime_shortest"] = [{"id": r["imdb_id"], "t": r["title"], "rt": int(r["runtime_min"]), "grp": group(r["imdb_id"])} for r in by_rt[::-1][:3]]

# ------------------------------------------------------------------ language and genre
S["language"] = series(lambda r: [r["primary_language"]])
for name in ("English", "Japanese", "French"):
    pair(f"language.{name.lower()}", lambda k: sum(1 for r in rows[k] if r["primary_language"] == name), 250)
pair("language.count", lambda k: len({r["primary_language"] for r in rows[k]}))
pair("language.silent", lambda k: sum(int(r["is_silent"]) for r in rows[k]))
pair("language.not_english", lambda k: sum(1 for r in rows[k] if r["primary_language"] != "English"), 250)
S["genre"] = sorted(series(lambda r: split(r["genres"])), key=lambda x: (-abs(x["gap_pp"]), x["name"]))
for x in S["genre"]:
    key = x["name"].lower().replace("-", "_")
    for side in ("imdb", "lb"):
        N[f"genre.{key}.{side}.n"], N[f"genre.{key}.{side}.pct"] = x[side], x[f"{side}_pct"]

# ------------------------------------------------------------------ directors
dc = {k: tally(k, lambda r: split(r["directors"])) for k in rows}
Di, Dl = set(dc[IM]), set(dc[LB])
pair("directors.distinct", lambda k: len(dc[k]))
N["directors.both"] = len(Di & Dl)
N["directors.imdb_only"], N["directors.lb_only"] = len(Di - Dl), len(Dl - Di)
put("directors.both.share_of.imdb", len(Di & Dl), len(Di))
put("directors.both.share_of.lb", len(Di & Dl), len(Dl))
N["directors.imdb_only.one_film"] = sum(dc[IM][d] == 1 for d in Di - Dl)
N["directors.lb_only.one_film"] = sum(dc[LB][d] == 1 for d in Dl - Di)
repeat = lambda k, m: {d for d, n in dc[k].items() if n >= m}
pair("directors.films_by_repeat", lambda k: sum(1 for r in rows[k] if any(d in repeat(k, 2) for d in split(r["directors"]))), 250)
pair("directors.3plus", lambda k: len(repeat(k, 3)))
N["directors.2plus_on_both"] = sum(1 for d in Di & Dl if dc[IM][d] >= 2 and dc[LB][d] >= 2)
fl = {k: {} for k in rows}
for k in rows:
    for r in rows[k]:
        for d in split(r["directors"]):
            fl[k].setdefault(d, set()).add(r["imdb_id"])
no_common = sorted(d for d in Di & Dl if not (fl[IM][d] & fl[LB][d]))
N["directors.shared_no_common_film"] = len(no_common)
pair("directors.films_by_shared", lambda k: sum(1 for r in rows[k] if any(d in Di & Dl for d in split(r["directors"]))), 250)
S["directors"] = sorted([{"name": d, "imdb": dc[IM].get(d, 0), "lb": dc[LB].get(d, 0)} for d in Di | Dl],
                        key=lambda x: (-(x["imdb"] + x["lb"]), x["name"]))
S["directors_shared_no_common_film"] = no_common
for d in Di | Dl:
    if max(dc[IM].get(d, 0), dc[LB].get(d, 0)) >= 4:
        N[f"director.{dslug(d)}.imdb"], N[f"director.{dslug(d)}.lb"] = dc[IM].get(d, 0), dc[LB].get(d, 0)

# ------------------------------------------------------------------ gender: directors
wf = {k: sum(int(r["has_woman_director"]) for r in rows[k]) for k in rows}
pair("gender.woman_director_films", lambda k: wf[k], 250, True)
N["gender.woman_director_films.distinct.n"] = sum(1 for r in distinct.values() if r["has_woman_director"] == "1")
N["gender.woman_director_films.distinct.of"] = len(distinct)
N["gender.woman_director_films.distinct.pct"] = pct1(N["gender.woman_director_films.distinct.n"], len(distinct))
for side, k in (("imdb", IM), ("lb", LB)):
    lo, hi = wilson(wf[k], 250)
    N[f"gender.woman_director_films.{side}.ci_low"], N[f"gender.woman_director_films.{side}.ci_high"] = lo, hi
N["gender.woman_director_films.gap_pp"] = round((wf[LB] - wf[IM]) * 100 / 250, 1)
N["gender.woman_director_films.ratio"] = round(wf[LB] / wf[IM], 2)
N["gender.woman_director_films.p"] = round(fisher(wf[IM], 250, wf[LB], 250), 2)
cw = {k: (sum(int(r["directors_women"]) for r in rows[k]), sum(int(r["directors_men"]) for r in rows[k])) for k in rows}
for side, k in (("imdb", IM), ("lb", LB)):
    w, m = cw[k]
    N[f"gender.director_credits.{side}.women"], N[f"gender.director_credits.{side}.men"] = w, m
    N[f"gender.director_credits.{side}.pct"] = pct1(w, w + m)
    N[f"gender.director_credits.{side}.men_per_woman"] = int(m / w + 0.5)
N["gender.director_credits.ratio"] = round((cw[LB][0] / sum(cw[LB])) / (cw[IM][0] / sum(cw[IM])), 2)
N["gender.director_credits.p"] = round(fisher(cw[IM][0], sum(cw[IM]), cw[LB][0], sum(cw[LB])), 2)
N["gender.director_mismatch_films"] = sum(1 for r in distinct.values() if r["gender_check"] == "count_differs")

# ------------------------------------------------------------------ gender: on screen and crew
gl = lambda k: [gcred[r["imdb_id"]] for r in rows[k] if r["imdb_id"] in gcred]
lead = {k: [int(x["lead_is_woman"]) for x in gl(k) if x["lead_is_woman"] != ""] for k in rows}
pair("gender.lead_woman", lambda k: sum(lead[k]), lambda k: len(lead[k]), True)
for side, k in (("imdb", IM), ("lb", LB)):
    lo, hi = wilson(sum(lead[k]), len(lead[k]))
    N[f"gender.lead_woman.{side}.ci_low"], N[f"gender.lead_woman.{side}.ci_high"] = lo, hi
N["gender.lead_woman.ratio"] = round((sum(lead[LB]) / len(lead[LB])) / (sum(lead[IM]) / len(lead[IM])), 1)
N["gender.lead_woman.p_below_0001"] = int(fisher(sum(lead[IM]), len(lead[IM]), sum(lead[LB]), len(lead[LB])) < 0.0001)
t3 = {k: (sum(int(x["top3_women"]) for x in gl(k)), sum(int(x["top3_n"]) for x in gl(k))) for k in rows}
pair("gender.top3_women", lambda k: t3[k][0], lambda k: t3[k][1], True)
N["gender.top3_women.p"] = round(fisher(t3[IM][0], t3[IM][1], t3[LB][0], t3[LB][1]), 3)
pair("gender.top3_no_woman", lambda k: sum(int(x["top3_women"]) == 0 for x in gl(k)))
pair("gender.top3_two_plus_women", lambda k: sum(int(x["top3_women"]) >= 2 for x in gl(k)))
ROLES = ["director", "writer", "producer", "editor", "cinematographer", "composer", "production_designer"]
S["crew"] = []
for role in ROLES:
    row = {"role": role}
    for side, k in (("imdb", IM), ("lb", LB)):
        w, m, u = (sum(int(x[f"{role}_{c}"]) for x in gl(k)) for c in ("women", "men", "unknown"))
        row[side] = {"women": w, "men": m, "unknown": u, "pct": pct1(w, w + m), "unknown_pct": pct(u, w + m + u)}
        for c, v in row[side].items():
            N[f"crew.{role}.{side}.{c}"] = v
    a, b = row["imdb"], row["lb"]
    row["p"] = round(fisher(a["women"], a["women"] + a["men"], b["women"], b["women"] + b["men"]), 2)
    N[f"crew.{role}.p"] = row["p"]
    S["crew"].append(row)

# ------------------------------------------------------------------ ratings, ranks, quadrants
mean2 = lambda xs: round(sum(xs) / len(xs), 2)
pair("rating.imdb_mean", lambda k: mean2([float(r["imdb_rating"]) for r in rows[k]]))
pair("rating.lb_mean", lambda k: mean2([float(r["lb_rating_10"]) for r in rows[k]]))
med_i = st.median(float(r["imdb_rating"]) for r in distinct.values())
med_l = round(st.median(float(r["lb_rating_10"]) for r in distinct.values()), 2)
N["rating.imdb_median_all"], N["rating.lb_median_all"] = med_i, med_l
pool = [r for r in rows[IM] if r["lb_rank500"]]
N["quadrant.rank.films"] = len(pool)
N["quadrant.rank.imdb_line"], N["quadrant.rank.lb_line"] = 125, 250
q = dict.fromkeys(["both", "lb", "imdb", "neither"], 0)
for r in pool:
    x, y = int(r["imdb_rank"]), int(r["lb_rank500"])
    q["both" if x <= 125 and y <= 250 else "lb" if x > 125 and y <= 250 else "imdb" if x <= 125 else "neither"] += 1
for k, v in q.items():
    N[f"quadrant.rank.{k}"] = v
rq = dict.fromkeys(["both_high", "imdb_higher", "lb_higher", "both_low"], 0)
for r in distinct.values():
    hl, hi = float(r["lb_rating_10"]) >= med_l, float(r["imdb_rating"]) >= med_i
    rq["both_high" if hl and hi else "imdb_higher" if hi else "lb_higher" if hl else "both_low"] += 1
for k, v in rq.items():
    N[f"quadrant.rating.{k}"] = v
ranked = [r for r in distinct.values() if r["imdb_rank"] and r["lb_rank500"]]
gap = sorted(ranked, key=lambda r: (-abs(int(r["imdb_rank"]) - int(r["lb_rank500"])), r["title"]))
S["rank_gap_top"] = [{"id": r["imdb_id"], "t": r["title"], "ir": int(r["imdb_rank"]), "lr": int(r["lb_rank500"])} for r in gap[:12]]

# ------------------------------------------------------------------ quiz baselines
pair("quiz.us", lambda k: sum(1 for r in rows[k] if r["country"] == "United States"), 250, True)

# ------------------------------------------------------------------ write
OUT.mkdir(parents=True, exist_ok=True)
meta_block = {"collected": COLLECTED, "source": "IMDb Top 250 and Letterboxd's official Top 500 (first 250 used)",
              "lists": {"imdb": "IMDb Top 250", "lb": "Letterboxd Top 250"}}
fields = {"id": "IMDb id", "t": "title (IMDb)", "aka": "other titles (Letterboxd)", "y": "year", "rt": "runtime, minutes (Letterboxd page)",
          "d": "directors", "g": "genres", "c": "main country (IMDb first-listed, modern name)", "cs": "all listed countries",
          "l": "main language", "s": "silent (1/0)", "ir": "IMDb rank (1-250)", "lr": "Letterboxd rank (1-500)",
          "iR": "IMDb rating", "iv": "IMDb votes", "lR": "Letterboxd rating out of 10", "lv": "Letterboxd ratings count",
          "grp": "imdb | both | lb | lb500 (Letterboxd 251-500 only, search only)", "wd": "has a woman director (1/0)",
          "wdn": "women directors", "lw": "first-billed performer is a woman (1/0)", "t3w": "women among top 3 billed", "t3n": "top 3 billed counted"}
json.dump({"meta": {**meta_block, "fields": fields}, "films": films}, open(OUT / "films.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
json.dump({"meta": meta_block, "n": dict(sorted(N.items())), "series": S}, open(OUT / "numbers.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"films.json: {len(films)} films | numbers.json: {len(N)} numbers, {len(S)} series -> {OUT.relative_to(ROOT)}")

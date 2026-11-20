"""Gate for the website's data files (data/site/films.json and data/site/numbers.json).

Run:   python3 -I scripts/check_export.py           (exit code 1 if anything fails)

Four checks, in order:
  1. STORY   scripts/check_numbers.py passes (the plan and the CSVs agree)
  2. FILMS   every record in films.json matches the CSVs it came from, field by field, and the set of films is complete
  3. NUMBERS every number and series in numbers.json is recomputed here from films.json (a different path from the
             export, which reads the CSVs) and must match. A key that this script does not recompute is a failure,
             so nothing can be shipped unchecked. Crew credits and director-credit counts are not in films.json, so those
             are recomputed from the CSVs.
  4. PLAN    the numbers the story plan states (the same figures check_numbers.py confirms) equal the shipped values.

The calculations are written fresh here and do not import export_site_data.py.
"""
import csv, json, math, subprocess, sys, statistics as st
from math import comb
from pathlib import Path
import re as _re, unicodedata as _ud
def dslug(name):
    """number-key slug for a director: 'Hirokazu Koreeda' -> 'hirokazu_koreeda'"""
    return _re.sub(r"[^a-z0-9]+", "_", _ud.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("_")

ROOT = Path(__file__).resolve().parent.parent
D, SITE = ROOT / "data", ROOT / "data" / "site"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8", newline="")))
sp = lambda s: [x.strip() for x in s.split(";") if x.strip()]
fails, passes = [], 0


def ok(cond, what):
    global passes
    if cond:
        passes += 1
    else:
        fails.append(what)


# ------------------------------------------------------------------ 1. STORY
r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "check_numbers.py"), "--quiet"], capture_output=True, text=True)
ok(r.returncode == 0, "check_numbers.py fails:\n" + r.stdout[-2000:])

# ------------------------------------------------------------------ 2. FILMS
FJ = json.load(open(SITE / "films.json", encoding="utf-8"))
NJ = json.load(open(SITE / "numbers.json", encoding="utf-8"))
films, N, S = FJ["films"], NJ["n"], NJ["series"]
by = {f["id"]: f for f in films}
ok(len(by) == len(films), "duplicate ids in films.json")

viz, uni = rd(D / "viz_films.csv"), rd(D / "unified.csv")
meta = {x["imdb_id"]: x for x in rd(ROOT / "raw" / "imdb_meta_for_lb_raw.csv")}
gc = {x["imdb_id"]: x for x in rd(D / "gender_credits.csv")}
vz = {}
for x in viz:
    vz.setdefault(x["imdb_id"], x)
on = {k: {x["imdb_id"] for x in viz if x["list"] == k} for k in ("IMDb250", "LB250")}
lb500 = {x["imdb_id"]: x for x in uni if x["list"] == "LB500"}
ok(set(by) == set(vz) | set(lb500), "films.json is not exactly the 389 films plus Letterboxd 251-500")


def same(fid, field, got, want):
    ok(got == want, f"films.json {fid} {field}: {got!r} != {want!r}")


for i, x in vz.items():
    f = by.get(i, {})
    grp = "both" if i in on["IMDb250"] and i in on["LB250"] else "imdb" if i in on["IMDb250"] else "lb"
    for field, want in [("t", x["title"]), ("y", int(x["year"])), ("rt", int(x["runtime_min"])), ("d", sp(x["directors"])),
                        ("g", sp(x["genres"])), ("c", x["country"]), ("cs", sp(x["countries"])), ("l", x["primary_language"]),
                        ("s", int(x["is_silent"])), ("ir", int(x["imdb_rank"]) if x["imdb_rank"] else None),
                        ("lr", int(x["lb_rank500"]) if x["lb_rank500"] else None), ("iR", float(x["imdb_rating"])),
                        ("iv", int(x["imdb_votes"])), ("lR", float(x["lb_rating_10"])), ("lv", int(x["lb_count"])),
                        ("grp", grp), ("wd", int(x["has_woman_director"]))]:
        same(i, field, f.get(field), want)
    g = gc.get(i)
    same(i, "lw", f.get("lw"), int(g["lead_is_woman"]) if g and g["lead_is_woman"] != "" else None)
    same(i, "t3w", f.get("t3w"), int(g["top3_women"]) if g else None)
    if f.get("wd"):
        ok(f.get("wdn") and all(n in f["d"] for n in f["wdn"]), f"{i} women director names not among its directors")
    ok(i in on["LB250"] or not f.get("lr") or f["lr"] > 250, f"{i} has a Letterboxd rank of 250 or better but is not on the Letterboxd list")
for i, x in lb500.items():
    if i in vz:
        continue
    f, m = by.get(i, {}), meta[i]
    for field, want in [("t", m["title"]), ("y", int(x["year"])), ("d", sp(x["directors"])), ("g", sp(x["genres"])),
                        ("c", sp(x["countries_modern"])[0]), ("l", x["primary_language"]), ("lr", int(x["rank"])),
                        ("iR", float(m["imdb_rating"])), ("lR", float(x["rating_10"])), ("grp", "lb500")]:
        same(i, field, f.get(field), want)
    ok(250 < f.get("lr", 0) <= 500, f"{i} Letterboxd-only extra outside ranks 251-500")
# The country rule must be the same for every film: first listed IMDb country, modern name.
modern = {x["raw"]: x["normalised"] for x in rd(D / "mappings" / "country_modern.csv")}
ok(all(f["c"] == modern.get(f["cs"][0], f["cs"][0]) for f in films), "a film's main country is not its first-listed IMDb country")

# ------------------------------------------------------------------ 3. NUMBERS (recomputed from films.json)
E, ES = {}, {}
IMf = [f for f in films if "ir" in f]
LBf = [f for f in films if f.get("lr", 999) <= 250]
L = {"imdb": IMf, "lb": LBf}
pct = lambda n, d: int(n / d * 100 + 0.5)
pct1 = lambda n, d: math.floor(n / d * 1000 + 0.5) / 10


def share(key, side, n, d, dec=False):
    E[f"{key}.{side}.n"], E[f"{key}.{side}.of"], E[f"{key}.{side}.pct"] = n, d, (pct1(n, d) if dec else pct(n, d))


def both_sides(key, f, d=None, dec=False):
    for s, fl in L.items():
        if d is None:
            E[f"{key}.{s}"] = f(fl)
        else:
            share(key, s, f(fl), d if isinstance(d, int) else d(fl), dec)


def fisher(a, n1, b, n2):
    k, n = a + b, n1 + n2
    p = lambda x: comb(n1, x) * comb(n2, k - x) / comb(n, k)
    p0 = p(a)
    return sum(p(x) for x in range(max(0, k - n2), min(n1, k) + 1) if p(x) <= p0 * (1 + 1e-9))


def wilson(k, n, z=1.959964):
    p, dn = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / dn, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / dn
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def counts(fl, key):
    c = {}
    for f in fl:
        for v in key(f):
            c[v] = c.get(v, 0) + 1
    return c


def ser(key):
    a, b = counts(IMf, key), counts(LBf, key)
    return {n: {"name": n, "imdb": a.get(n, 0), "lb": b.get(n, 0), "imdb_pct": pct(a.get(n, 0), 250), "lb_pct": pct(b.get(n, 0), 250),
                "gap_pp": round((b.get(n, 0) - a.get(n, 0)) * 100 / 250, 1)} for n in set(a) | set(b)}


grp = counts(films, lambda f: [f["grp"]])
chart = [f for f in films if f["grp"] != "lb500"]
E["lists.size"] = 250
E["overlap.both"], E["overlap.imdb_only"], E["overlap.lb_only"] = grp["both"], grp["imdb"], grp["lb"]
E["overlap.distinct"] = len(chart)
E["overlap.imdb_only.lb251_500"] = sum(1 for f in IMf if f.get("lr", 0) > 250)
E["overlap.imdb_only.not_in_lb500"] = sum(1 for f in IMf if "lr" not in f)
E["search.films"], E["search.lb251_500_only"] = len(films), grp["lb500"]

ES["country"] = ser(lambda f: [f["c"]])
for name, key in [("United States", "us"), ("Japan", "japan"), ("United Kingdom", "uk"), ("France", "france"), ("Italy", "italy"),
                  ("India", "india"), ("Germany", "germany"), ("Russia", "russia"), ("Iran", "iran"), ("Sweden", "sweden"), ("South Korea", "korea")]:
    both_sides(f"country.{key}", lambda fl: sum(f["c"] == name for f in fl), 250)
LEAN = {"United States", "Japan", "United Kingdom", "Italy", "France", "India", "Germany", "Russia", "Iran", "Sweden", "South Korea"}
both_sides("country.rest", lambda fl: sum(f["c"] not in LEAN for f in fl), 250)
both_sides("country.count", lambda fl: len({f["c"] for f in fl}))
both_sides("country.top3", lambda fl: sum(sorted(counts(fl, lambda f: [f["c"]]).values())[-3:]), 250)
both_sides("country.coproduction", lambda fl: sum(len(f["cs"]) > 1 for f in fl), 250)

both_sides("year.median", lambda fl: st.median(f["y"] for f in fl))
both_sides("year.mean", lambda fl: round(st.mean(f["y"] for f in fl), 1))
both_sides("year.since2000", lambda fl: sum(f["y"] >= 2000 for f in fl), 250)
both_sides("year.before1970", lambda fl: sum(f["y"] < 1970 for f in fl), 250)
both_sides("year.earliest", lambda fl: min(f["y"] for f in fl))
both_sides("year.latest", lambda fl: max(f["y"] for f in fl))
ES["decade"] = {}
for f in chart:
    dk = f"{f['y'] // 10 * 10}s"
    ES["decade"].setdefault(dk, {"name": dk, "imdb": 0, "lb": 0})
lo, hi = min(int(k[:4]) for k in ES["decade"]), max(int(k[:4]) for k in ES["decade"])
for dd in range(lo, hi + 1, 10):
    dk = f"{dd}s"
    row = ES["decade"].setdefault(dk, {"name": dk, "imdb": 0, "lb": 0})
    row["imdb"], row["lb"] = sum(f["y"] // 10 * 10 == dd for f in IMf), sum(f["y"] // 10 * 10 == dd for f in LBf)
    E[f"decade.{dk}.imdb"], E[f"decade.{dk}.lb"] = row["imdb"], row["lb"]

both_sides("runtime.median", lambda fl: st.median(f["rt"] for f in fl))
both_sides("runtime.mean", lambda fl: round(st.mean(f["rt"] for f in fl)))
both_sides("runtime.2h_plus", lambda fl: sum(f["rt"] >= 120 for f in fl), 250)
both_sides("runtime.3h_plus", lambda fl: sum(f["rt"] >= 180 for f in fl))
both_sides("runtime.under90", lambda fl: sum(f["rt"] < 90 for f in fl))
srt = sorted(chart, key=lambda f: (f["rt"], f["t"]))
longest = sorted(chart, key=lambda f: (-f["rt"], f["t"]))[:5]
shortest = sorted(chart, key=lambda f: (f["rt"], [-ord(c) for c in f["t"]]))[:3]

ES["language"] = ser(lambda f: [f["l"]])
for name in ("English", "Japanese", "French"):
    both_sides(f"language.{name.lower()}", lambda fl: sum(f["l"] == name for f in fl), 250)
both_sides("language.count", lambda fl: len({f["l"] for f in fl}))
both_sides("language.silent", lambda fl: sum(f["s"] for f in fl))
both_sides("language.not_english", lambda fl: sum(f["l"] != "English" for f in fl), 250)
ES["genre"] = ser(lambda f: f["g"])
for g, row in ES["genre"].items():
    k = g.lower().replace("-", "_")
    for s in ("imdb", "lb"):
        E[f"genre.{k}.{s}.n"], E[f"genre.{k}.{s}.pct"] = row[s], row[f"{s}_pct"]

dc = {s: counts(fl, lambda f: f["d"]) for s, fl in L.items()}
Di, Dl = set(dc["imdb"]), set(dc["lb"])
both_sides("directors.distinct", lambda fl: len(counts(fl, lambda f: f["d"])))
E["directors.both"], E["directors.imdb_only"], E["directors.lb_only"] = len(Di & Dl), len(Di - Dl), len(Dl - Di)
for s, ds in (("imdb", Di), ("lb", Dl)):
    E[f"directors.both.share_of.{s}.n"], E[f"directors.both.share_of.{s}.of"], E[f"directors.both.share_of.{s}.pct"] = len(Di & Dl), len(ds), pct(len(Di & Dl), len(ds))
E["directors.imdb_only.one_film"] = sum(1 for d in Di - Dl if dc["imdb"][d] == 1)
E["directors.lb_only.one_film"] = sum(1 for d in Dl - Di if dc["lb"][d] == 1)
for s, fl in L.items():
    share("directors.films_by_repeat", s, sum(any(dc[s][d] > 1 for d in f["d"]) for f in fl), 250)
    E[f"directors.3plus.{s}"] = sum(n >= 3 for n in dc[s].values())
    share("directors.films_by_shared", s, sum(any(d in Di and d in Dl for d in f["d"]) for f in fl), 250)
E["directors.2plus_on_both"] = sum(1 for d in Di & Dl if min(dc["imdb"][d], dc["lb"][d]) >= 2)
nocommon = sorted(d for d in Di & Dl if not any(d in f["d"] for f in films if f["grp"] == "both"))
E["directors.shared_no_common_film"] = len(nocommon)
ES["directors"] = {d: {"name": d, "imdb": dc["imdb"].get(d, 0), "lb": dc["lb"].get(d, 0)} for d in Di | Dl}
for d in Di | Dl:
    if max(dc["imdb"].get(d, 0), dc["lb"].get(d, 0)) >= 4:
        E[f"director.{dslug(d)}.imdb"], E[f"director.{dslug(d)}.lb"] = dc["imdb"].get(d, 0), dc["lb"].get(d, 0)

for s, fl in L.items():
    k = sum(f["wd"] for f in fl)
    share("gender.woman_director_films", s, k, 250, True)
    E[f"gender.woman_director_films.{s}.ci_low"], E[f"gender.woman_director_films.{s}.ci_high"] = wilson(k, 250)
wi, wl = sum(f["wd"] for f in IMf), sum(f["wd"] for f in LBf)
wdist = sum(f.get("wd", 0) for f in chart)
E["gender.woman_director_films.distinct.n"], E["gender.woman_director_films.distinct.of"] = wdist, len(chart)
E["gender.woman_director_films.distinct.pct"] = pct1(wdist, len(chart))
E["gender.woman_director_films.gap_pp"] = round((wl - wi) * 100 / 250, 1)
E["gender.woman_director_films.ratio"] = round(wl / wi, 2)
E["gender.woman_director_films.p"] = round(fisher(wi, 250, wl, 250), 2)
# director credits by gender are not in films.json: recompute from the CSV
cred = {}
for s, lst in (("imdb", "IMDb250"), ("lb", "LB250")):
    w = sum(int(x["directors_women"]) for x in viz if x["list"] == lst)
    m = sum(int(x["directors_men"]) for x in viz if x["list"] == lst)
    cred[s] = (w, m)
    E[f"gender.director_credits.{s}.women"], E[f"gender.director_credits.{s}.men"] = w, m
    E[f"gender.director_credits.{s}.pct"] = pct1(w, w + m)
    E[f"gender.director_credits.{s}.men_per_woman"] = round(m / w)
E["gender.director_credits.ratio"] = round((cred["lb"][0] / sum(cred["lb"])) / (cred["imdb"][0] / sum(cred["imdb"])), 2)
E["gender.director_credits.p"] = round(fisher(cred["imdb"][0], sum(cred["imdb"]), cred["lb"][0], sum(cred["lb"])), 2)
E["gender.director_mismatch_films"] = sum(1 for x in vz.values() if x["gender_check"] != "ok")

lead = {s: [f["lw"] for f in fl if "lw" in f] for s, fl in L.items()}
for s in L:
    share("gender.lead_woman", s, sum(lead[s]), len(lead[s]), True)
    E[f"gender.lead_woman.{s}.ci_low"], E[f"gender.lead_woman.{s}.ci_high"] = wilson(sum(lead[s]), len(lead[s]))
E["gender.lead_woman.ratio"] = round((sum(lead["lb"]) / len(lead["lb"])) / (sum(lead["imdb"]) / len(lead["imdb"])), 1)
E["gender.lead_woman.p_below_0001"] = int(fisher(sum(lead["imdb"]), len(lead["imdb"]), sum(lead["lb"]), len(lead["lb"])) < 0.0001)
t3 = {s: (sum(f.get("t3w", 0) for f in fl), sum(f.get("t3n", 0) for f in fl)) for s, fl in L.items()}
for s in L:
    share("gender.top3_women", s, *t3[s], True)
    E[f"gender.top3_no_woman.{s}"] = sum(1 for f in L[s] if "t3w" in f and f["t3w"] == 0)
    E[f"gender.top3_two_plus_women.{s}"] = sum(1 for f in L[s] if f.get("t3w", 0) >= 2)
E["gender.top3_women.p"] = round(fisher(t3["imdb"][0], t3["imdb"][1], t3["lb"][0], t3["lb"][1]), 3)
ES["crew"] = {}
for role in ["director", "writer", "producer", "editor", "cinematographer", "composer", "production_designer"]:
    row = {"role": role}
    for s, fl in L.items():
        w, m, u = (sum(int(gc[f["id"]][f"{role}_{c}"]) for f in fl if f["id"] in gc) for c in ("women", "men", "unknown"))
        row[s] = {"women": w, "men": m, "unknown": u, "pct": pct1(w, w + m), "unknown_pct": pct(u, w + m + u)}
        for c, v in row[s].items():
            E[f"crew.{role}.{s}.{c}"] = v
    a, b = row["imdb"], row["lb"]
    row["p"] = E[f"crew.{role}.p"] = round(fisher(a["women"], a["women"] + a["men"], b["women"], b["women"] + b["men"]), 2)
    ES["crew"][role] = row

for s, fl in L.items():
    E[f"rating.imdb_mean.{s}"] = round(sum(f["iR"] for f in fl) / len(fl), 2)
    E[f"rating.lb_mean.{s}"] = round(sum(f["lR"] for f in fl) / len(fl), 2)
mi, ml = st.median(f["iR"] for f in chart), round(st.median(f["lR"] for f in chart), 2)
E["rating.imdb_median_all"], E["rating.lb_median_all"] = mi, ml
pool = [f for f in IMf if "lr" in f]
E["quadrant.rank.films"], E["quadrant.rank.imdb_line"], E["quadrant.rank.lb_line"] = len(pool), 125, 250
E["quadrant.rank.both"] = sum(f["ir"] <= 125 and f["lr"] <= 250 for f in pool)
E["quadrant.rank.lb"] = sum(f["ir"] > 125 and f["lr"] <= 250 for f in pool)
E["quadrant.rank.imdb"] = sum(f["ir"] <= 125 and f["lr"] > 250 for f in pool)
E["quadrant.rank.neither"] = sum(f["ir"] > 125 and f["lr"] > 250 for f in pool)
E["quadrant.rating.both_high"] = sum(f["iR"] >= mi and f["lR"] >= ml for f in chart)
E["quadrant.rating.imdb_higher"] = sum(f["iR"] >= mi and f["lR"] < ml for f in chart)
E["quadrant.rating.lb_higher"] = sum(f["iR"] < mi and f["lR"] >= ml for f in chart)
E["quadrant.rating.both_low"] = sum(f["iR"] < mi and f["lR"] < ml for f in chart)
gaps = sorted([f for f in chart if "ir" in f and "lr" in f], key=lambda f: (-abs(f["ir"] - f["lr"]), f["t"]))[:12]
for s, fl in L.items():
    share("quiz.us", s, sum(f["c"] == "United States" for f in fl), 250, True)

# compare scalars: every shipped key must be recomputed, and every recomputed key shipped
for k in sorted(set(N) | set(E)):
    if k not in E:
        fails.append(f"numbers.json key not recomputed by the gate: {k}")
    elif k not in N:
        fails.append(f"numbers.json is missing {k}")
    else:
        a, b = N[k], E[k]
        ok(a == b or (isinstance(a, float) and isinstance(b, (int, float)) and abs(a - b) < 1e-9), f"{k}: shipped {a!r}, recomputed {b!r}")

# compare series
def same_rows(name, shipped, expected, key="name"):
    ok(len(shipped) == len(expected) and all(r[key] in expected and r == expected[r[key]] for r in shipped),
       f"series {name} differs from recomputation")


for name in ("country", "language", "genre", "decade", "directors"):
    same_rows(name, S[name], ES[name])
same_rows("crew", S["crew"], ES["crew"], "role")
ok([d["name"] for d in S["decade"]] == sorted(ES["decade"]), "decade series is not in order or has gaps")
ok(S["runtime_longest"] == [{"id": f["id"], "t": f["t"], "rt": f["rt"], "grp": f["grp"]} for f in longest], "series runtime_longest differs")
ok([x["rt"] for x in S["runtime_shortest"]] == [f["rt"] for f in srt[:3]], "series runtime_shortest differs")
ok(S["rank_gap_top"] == [{"id": f["id"], "t": f["t"], "ir": f["ir"], "lr": f["lr"]} for f in gaps], "series rank_gap_top differs")
ok(S["directors_shared_no_common_film"] == nocommon, "series directors_shared_no_common_film differs")
ok(set(S) == {"country", "language", "genre", "decade", "directors", "crew", "runtime_longest", "runtime_shortest",
              "rank_gap_top", "directors_shared_no_common_film"}, f"unexpected series set: {sorted(S)}")

# ------------------------------------------------------------------ 4. PLAN (the figures STORY_PLAN.md states)
PLAN = {
    "overlap.both": 111, "overlap.imdb_only": 139, "overlap.lb_only": 139, "overlap.distinct": 389,
    "overlap.imdb_only.lb251_500": 60, "overlap.imdb_only.not_in_lb500": 79, "search.films": 579,
    "country.us.imdb.n": 145, "country.us.imdb.pct": 58, "country.us.lb.n": 83, "country.us.lb.pct": 33,
    "country.japan.imdb.pct": 8, "country.japan.lb.pct": 19, "country.uk.imdb.pct": 12, "country.uk.lb.pct": 6,
    "country.france.imdb.pct": 3, "country.france.lb.pct": 7, "country.italy.imdb.pct": 4, "country.italy.lb.pct": 7,
    "country.count.imdb": 23, "country.count.lb": 33, "country.top3.imdb.pct": 78, "country.top3.lb.pct": 59,
    "country.coproduction.imdb.pct": 39, "country.coproduction.lb.pct": 37,
    "year.median.imdb": 1997, "year.median.lb": 1987.5, "year.since2000.imdb.pct": 44, "year.since2000.lb.pct": 33,
    "year.before1970.imdb.pct": 24, "year.before1970.lb.pct": 34, "decade.2000s.imdb": 48, "decade.2010s.imdb": 44,
    "decade.1990s.imdb": 39, "decade.1960s.lb": 36, "decade.1990s.lb": 37, "decade.2000s.lb": 36, "decade.1950s.lb": 33,
    "decade.2020s.lb": 24, "decade.2020s.imdb": 18,
    "runtime.median.imdb": 129, "runtime.median.lb": 125, "runtime.mean.imdb": 132, "runtime.mean.lb": 131,
    "runtime.2h_plus.imdb.pct": 62, "runtime.2h_plus.lb.pct": 61, "runtime.3h_plus.imdb": 17, "runtime.3h_plus.lb": 20,
    "runtime.under90.imdb": 17, "runtime.under90.lb": 20,
    "language.english.imdb.n": 187, "language.english.lb.n": 110, "language.japanese.imdb.n": 19, "language.japanese.lb.n": 47,
    "language.french.imdb.n": 5, "language.french.lb.n": 15, "language.silent.imdb": 6,
    "genre.drama.imdb.pct": 74, "genre.drama.lb.pct": 89, "genre.adventure.imdb.pct": 26, "genre.adventure.lb.pct": 14,
    "genre.action.imdb.pct": 17, "genre.action.lb.pct": 8, "genre.sci_fi.imdb.pct": 13, "genre.sci_fi.lb.pct": 8,
    "genre.crime.imdb.pct": 22, "genre.crime.lb.pct": 16, "genre.romance.imdb.pct": 10, "genre.romance.lb.pct": 15,
    "directors.distinct.imdb": 181, "directors.distinct.lb": 176, "directors.both": 84, "directors.imdb_only": 97,
    "directors.lb_only": 92, "directors.both.share_of.imdb.pct": 46, "directors.both.share_of.lb.pct": 48,
    "directors.imdb_only.one_film": 84, "directors.lb_only.one_film": 70, "directors.films_by_repeat.imdb.pct": 56,
    "directors.films_by_repeat.lb.pct": 59, "directors.3plus.imdb": 23, "directors.3plus.lb": 21, "directors.2plus_on_both": 22,
    "directors.shared_no_common_film": 2, "directors.films_by_shared.imdb.pct": 64, "directors.films_by_shared.lb.pct": 56,
    "gender.woman_director_films.imdb.n": 4, "gender.woman_director_films.imdb.pct": 1.6, "gender.woman_director_films.lb.n": 7,
    "gender.woman_director_films.lb.pct": 2.8, "gender.woman_director_films.distinct.n": 10, "gender.woman_director_films.distinct.pct": 2.6,
    "gender.woman_director_films.imdb.ci_low": 0.6, "gender.woman_director_films.imdb.ci_high": 4.0,
    "gender.woman_director_films.lb.ci_low": 1.4, "gender.woman_director_films.lb.ci_high": 5.7,
    "gender.woman_director_films.ratio": 1.75, "gender.woman_director_films.gap_pp": 1.2, "gender.woman_director_films.p": 0.54,
    "gender.director_credits.imdb.women": 5, "gender.director_credits.imdb.men": 276, "gender.director_credits.imdb.pct": 1.8,
    "gender.director_credits.imdb.men_per_woman": 55, "gender.director_credits.lb.women": 7, "gender.director_credits.lb.men": 263,
    "gender.director_credits.lb.pct": 2.6, "gender.director_credits.lb.men_per_woman": 38, "gender.director_credits.ratio": 1.46,
    "gender.director_credits.p": 0.57, "gender.director_mismatch_films": 12,
    "gender.lead_woman.imdb.n": 24, "gender.lead_woman.imdb.of": 249, "gender.lead_woman.imdb.pct": 9.6,
    "gender.lead_woman.lb.n": 59, "gender.lead_woman.lb.of": 250, "gender.lead_woman.lb.pct": 23.6,
    "gender.lead_woman.imdb.ci_low": 6.6, "gender.lead_woman.imdb.ci_high": 13.9, "gender.lead_woman.lb.ci_low": 18.8,
    "gender.lead_woman.lb.ci_high": 29.2, "gender.lead_woman.p_below_0001": 1,
    "gender.top3_women.imdb.n": 191, "gender.top3_women.imdb.of": 747, "gender.top3_women.imdb.pct": 25.6,
    "gender.top3_women.lb.n": 245, "gender.top3_women.lb.of": 748, "gender.top3_women.lb.pct": 32.8, "gender.top3_women.p": 0.003,
    "gender.top3_no_woman.imdb": 91, "gender.top3_no_woman.lb": 73, "gender.top3_two_plus_women.imdb": 31, "gender.top3_two_plus_women.lb": 61,
    "crew.director.imdb.pct": 1.5, "crew.director.lb.pct": 1.9,
    "crew.writer.imdb.pct": 8.8, "crew.writer.lb.pct": 7.7, "crew.writer.p": 0.58,
    "crew.producer.imdb.pct": 17.0, "crew.producer.lb.pct": 14.2, "crew.producer.p": 0.32,
    "crew.editor.imdb.pct": 16.9, "crew.editor.lb.pct": 21.0, "crew.editor.p": 0.23,
    "crew.cinematographer.imdb.pct": 1.7, "crew.cinematographer.lb.pct": 2.9, "crew.composer.imdb.pct": 4.4, "crew.composer.lb.pct": 2.2,
    "crew.production_designer.imdb.pct": 11.9, "crew.production_designer.lb.pct": 17.4,
    "rating.imdb_mean.imdb": 8.31, "rating.imdb_mean.lb": 8.18, "rating.lb_mean.imdb": 8.47, "rating.lb_mean.lb": 8.71,
    "rating.imdb_median_all": 8.2, "rating.lb_median_all": 8.56, "quadrant.rank.films": 171,
    "quadrant.rank.both": 73, "quadrant.rank.lb": 38, "quadrant.rank.imdb": 28, "quadrant.rank.neither": 32,
    "quadrant.rating.both_high": 111, "quadrant.rating.imdb_higher": 96, "quadrant.rating.lb_higher": 91, "quadrant.rating.both_low": 91,
}
for k, v in PLAN.items():
    ok(k in N and abs(N[k] - v) < 1e-9, f"plan states {k} = {v}, shipped {N.get(k)!r}")
CREW_COUNTS = {"writer": ((49, 510), (40, 482)), "producer": ((70, 341), (50, 303)), "editor": ((50, 245), (53, 199)),
               "cinematographer": ((4, 235), (7, 238)), "composer": ((11, 237), (5, 220)), "production_designer": ((20, 148), (26, 123))}
for role, ((iw, im), (lw, lm)) in CREW_COUNTS.items():
    ok((N[f"crew.{role}.imdb.women"], N[f"crew.{role}.imdb.men"], N[f"crew.{role}.lb.women"], N[f"crew.{role}.lb.men"]) == (iw, im, lw, lm),
       f"plan crew counts for {role} differ from shipped")
dirs = {d["name"]: (d["imdb"], d["lb"]) for d in S["directors"]}
for name, v in {"Christopher Nolan": (9, 5), "Akira Kurosawa": (6, 9), "Andrei Tarkovsky": (0, 5), "Ingmar Bergman": (2, 6),
                "Steven Spielberg": (7, None), "Martin Scorsese": (7, None), "Stanley Kubrick": (7, None), "Quentin Tarantino": (6, None),
                "Billy Wilder": (None, 6), "Masaki Kobayashi": (None, 5), "Hirokazu Koreeda": (None, 4), "Abbas Kiarostami": (None, 4)}.items():
    got = dirs.get(name, (0, 0))
    ok(all(w is None or g == w for g, w in zip(got, v)), f"plan states {name} = {v}, shipped {got}")
ok(S["directors_shared_no_common_film"] == ["Wes Anderson", "William Friedkin"], "plan names Wes Anderson and William Friedkin")
for title, ir, lr in [("Inception", 13, 248), ("Alien", 51, 246), ("The Battle of Algiers", 244, 28), ("La haine", 226, 20),
                      ("The Passion of Joan of Arc", 249, 54), ("The Shawshank Redemption", 1, 7), ("Harakiri", 37, 1)]:
    f = next((f for f in films if f["t"] == title), {})
    ok((f.get("ir"), f.get("lr")) == (ir, lr), f"plan states {title} is IMDb #{ir} / Letterboxd #{lr}, shipped {f.get('ir')}/{f.get('lr')}")
ok([x["rt"] for x in S["runtime_longest"][:3]] == [432, 367, 254] and S["runtime_shortest"][0]["rt"] == 45, "plan's longest/shortest runtimes")

# ------------------------------------------------------------------ 5. LAYOUTS (precomputed dot positions)
import re
LJ = json.load(open(SITE / "layouts.json", encoding="utf-8"))["layouts"]
entries = {f"{f['id']}:i" for f in IMf} | {f"{f['id']}:l" for f in LBf}
dir_names = {d["name"] for d in S["directors"]}
films_of = lambda d: {f["id"] for f in chart if d in f["d"]}
want_keys = {
    "ladder": entries, "hook.split": entries, "hook.merge": entries, "country.lean": entries,
    "ranks.ladder": entries | {f"{f['id']}:l" for f in IMf if f.get("lr", 0) > 250}, "womendir.grid": entries,
    "directors.lean": {f"s:{d['name']}|{f['id']}:{s}" for d in S["directors"] if max(d["imdb"], d["lb"]) >= 4
                       for s, fl in (("i", IMf), ("l", LBf)) for f in fl if d["name"] in f["d"]}, "overlap.lists": entries, "overlap.groups": entries, "country.rows": entries, "year.swarm": entries,
    "runtime.swarm": entries, "waffle.lead": entries, "quadrant.rank": {f["id"] for f in pool},
    "quadrant.rating": {f["id"] for f in chart}, "directors.sort": {f"d:{d}" for d in dir_names},
    "directors.strips": {f"s:{d['name']}|{i}" for d in S["directors"] if max(d["imdb"], d["lb"]) >= 4 for i in films_of(d["name"])},
}
ok(set(LJ) == set(want_keys), f"layouts present: {sorted(LJ)}")
fid = lambda k: k.split("|")[-1].split(":")[0] if not k.startswith("d:") else None
val_of = {"i": lambda f: f["ir"], "l": lambda f: f["lr"]}


def monotone(pairs, what):
    """pairs: (value, coordinate). Larger value must never sit at a smaller coordinate; equal values share one."""
    pairs = sorted(pairs)
    bad = [(a, b) for a, b in zip(pairs, pairs[1:]) if (a[0] < b[0] and a[1] > b[1] + 1e-6) or (a[0] == b[0] and abs(a[1] - b[1]) > 1e-6)]
    ok(not bad, f"{what}: positions do not follow the data ({bad[:2]})")


for name, lay in LJ.items():
    ks = lay["keys"]
    ok(set(ks) == want_keys.get(name, set()) and len(ks) == len(set(ks)), f"layout {name}: wrong set of dots")
    for vname in ("wide", "narrow"):
        v = lay[vname]
        xy = v["xy"]
        ok(len(xy) == 2 * len(ks), f"{name}/{vname}: xy length")
        P = {k: (xy[2 * j], xy[2 * j + 1]) for j, k in enumerate(ks)}
        rad = dict(zip(ks, v.get("radii", [v["r"]] * len(ks))))
        ok(all(rad[k] <= x <= v["w"] - rad[k] + 0.05 and rad[k] - 0.05 <= y <= v["h"] - rad[k] for k, (x, y) in P.items()), f"{name}/{vname}: a dot is outside the frame")
        # no overlapping dots, except where overlap is the design (rank ladder, scatters) or the same film on both lists
        if name not in ("ladder", "ranks.ladder", "quadrant.rank", "quadrant.rating"):
            cell, buckets, clash = 2 * max(rad.values()) + 1, {}, []
            for k, (x, y) in P.items():
                buckets.setdefault((int(x // cell), int(y // cell)), []).append(k)
            for k, (x, y) in P.items():
                cx, cy = int(x // cell), int(y // cell)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for k2 in buckets.get((cx + dx, cy + dy), []):
                            if k2 <= k or fid(k) == fid(k2):
                                continue
                            x2, y2 = P[k2]
                            if math.hypot(x - x2, y - y2) < rad[k] + rad[k2] - 0.05:
                                clash.append((k, k2))
            ok(not clash, f"{name}/{vname}: {len(clash)} overlapping dots, e.g. {clash[:2]}")
        if name == "overlap.groups":
            ok(all(P[f"{i}:i"] == P[f"{i}:l"] for i in by if by[i]["grp"] == "both"), f"{name}/{vname}: a shared film is split")
        # positions encode the data
        if name in ("year.swarm", "runtime.swarm"):
            fld = "y" if name == "year.swarm" else "rt"
            monotone([(by[fid(k)][fld], P[k][0]) for k in ks], f"{name}/{vname} x")
            ok(all(P[k][1] < min(P[j][1] for j in ks if j.endswith(":l")) for k in ks if k.endswith(":i")), f"{name}/{vname}: IMDb row is not above Letterboxd row")
        if name == "ladder":
            for s in "il":
                monotone([(val_of[s](by[fid(k)]), P[k][1]) for k in ks if k.endswith(":" + s)], f"ladder/{vname} {s}")
        if name == "quadrant.rank":
            monotone([(by[k]["ir"], P[k][0]) for k in ks], f"{name}/{vname} x")
            monotone([(by[k]["lr"], P[k][1]) for k in ks], f"{name}/{vname} y")
        if name == "quadrant.rating":
            monotone([(-by[k]["lR"], P[k][1]) for k in ks], f"{name}/{vname} y")
            xs = sorted((by[k]["iR"], P[k][0]) for k in ks)
            ok(all(a[1] < b[1] for a, b in zip(xs, xs[1:]) if a[0] < b[0] - 1e-9), f"{name}/{vname}: jitter crosses an IMDb rating step")
        if name == "directors.strips":
            for d in lay["rows"]:
                monotone([(by[fid(k)]["y"], P[k][0]) for k in ks if k.startswith(f"s:{d}|")], f"strips/{vname} {d}")
        if name == "waffle.lead":
            for s, side in (("i", "imdb"), ("l", "lb")):
                cells = sorted((P[k][1], P[k][0], by[fid(k)].get("lw")) for k in ks if k.endswith(":" + s))
                n = N[f"gender.lead_woman.{side}.n"]
                ok([c[2] for c in cells[:n]] == [1] * n and 1 not in [c[2] for c in cells[n:]], f"waffle/{vname} {s}: women-led films are not the first {n} squares")
        if name == "country.rows":
            rows = sorted((l["y"], l["t"]) for l in v["deco"]["labels"] if l["c"] == "row")
            named = {l for _, l in rows} - {"Other countries"}
            for k, (x, y) in P.items():
                lab = min(rows, key=lambda r: abs(r[0] - y))[1]
                c = by[fid(k)]["c"]
                ok(lab == (c if c in named else "Other countries"), f"country/{vname}: {k} ({c}) drawn in row {lab}")
                ok((x < v["w"] / 2) == k.endswith(":i"), f"country/{vname}: {k} on the wrong side")
        if name == "country.lean":
            cx, rows_v = v["w"] / 2, v["rows"]
            ok([r["t"] for r in rows_v] == lay["rows"], f"country.lean/{vname}: row bands do not match the row order")
            band = {r["t"]: r for r in rows_v}
            rowof = lambda f: f["c"] if f["c"] in LEAN else "Other countries"
            for k, (x, y) in P.items():
                f = by[fid(k)]
                b = band[rowof(f)]
                ok(b["y0"] < y < b["y1"], f"country.lean/{vname}: {k} ({f['c']}) is not inside its row")
                ok((x < cx) == k.endswith(":i"), f"country.lean/{vname}: {k} on the wrong side of the centre line")
            for r in rows_v:
                for s, side in (("i", "imdb"), ("l", "lb")):
                    sk = [k for k in ks if k.endswith(":" + s) and rowof(by[fid(k)]) == r["t"]]
                    want = N[f"country.{r['key']}.{side}.n"]
                    ok(len(sk) == want, f"country.lean/{vname}: {r['t']} {side} has {len(sk)} dots, numbers.json says {want}")
                    sh = [abs(P[k][0] - cx) for k in sk if by[fid(k)]["grp"] == "both"]
                    ot = [abs(P[k][0] - cx) for k in sk if by[fid(k)]["grp"] != "both"]
                    ok(not sh or not ot or max(sh) <= min(ot) + 1e-6, f"country.lean/{vname}: {r['t']} {side}: a shared film is not next to the centre line")
            leans = [N[f"country.{r['key']}.lb.n"] - N[f"country.{r['key']}.imdb.n"] for r in rows_v if r["key"] != "rest"]
            ok(leans == sorted(leans) and rows_v[-1]["key"] == "rest", f"country.lean/{vname}: rows are not ordered from IMDb-leaning to Letterboxd-leaning")
        if name == "womendir.grid":
            cx = v["w"] / 2
            for k, (x, y) in P.items():
                ok((x < cx) == k.endswith(":i"), f"womendir.grid/{vname}: {k} on the wrong side of the centre line")
            for s, side in (("i", "imdb"), ("l", "lb")):
                # fill order: row by row from the top, starting next to the line
                cells = sorted((P[k][1], abs(P[k][0] - cx), by[fid(k)]["wd"]) for k in ks if k.endswith(":" + s))
                n_ = N[f"gender.woman_director_films.{side}.n"]
                ok([c[2] for c in cells[:n_]] == [1] * n_ and 1 not in [c[2] for c in cells[n_:]],
                   f"womendir.grid/{vname} {side}: films directed by women are not the first {n_} dots")
        if name == "hook.split":
            cx = v["w"] / 2
            for s_ in "il":
                sk = [k for k in ks if k.endswith(":" + s_)]
                ok(all((P[k][0] < cx) == (s_ == "i") for k in sk), f"hook.split/{vname}: a {s_} dot on the wrong side")
                # fill order (row by row from the top, starting next to the line) follows rank
                order_ = [val_of[s_](by[fid(k)]) for k in sorted(sk, key=lambda k: (P[k][1], abs(P[k][0] - cx)))]
                ok(order_ == sorted(order_), f"hook.split/{vname} {s_}: dots are not in rank order")
        if name == "hook.merge":
            shared_ = [i for i in by if by[i]["grp"] == "both"]
            ok(all(P[f"{i}:i"] == P[f"{i}:l"] for i in shared_), f"hook.merge/{vname}: a shared film's two dots don't meet")
            xs_ = {g: [P[k][0] for k in ks if by[fid(k)]["grp"] == g] for g in ("imdb", "both", "lb")}
            ok(max(xs_["imdb"]) < min(xs_["both"]) and max(xs_["both"]) < min(xs_["lb"]), f"hook.merge/{vname}: the three groups are not left, centre, right")
            ok((len(xs_["imdb"]), len(set(map(tuple, (P[f"{i}:i"] for i in shared_)))), len(xs_["lb"])) ==
               (N["overlap.imdb_only"], N["overlap.both"], N["overlap.lb_only"]), f"hook.merge/{vname}: group sizes differ from numbers.json")
        if name == "ranks.ladder":
            cx = v["w"] / 2
            for s_ in "il":
                sk = [k for k in ks if k.endswith(":" + s_)]
                ok(all((P[k][0] < cx) == (s_ == "i") for k in sk), f"ranks.ladder/{vname}: a {s_} dot on the wrong side")
                monotone([(val_of[s_](by[fid(k)]), P[k][1]) for k in sk], f"ranks.ladder/{vname} {s_}")
            ok(sum(1 for k in ks if k.endswith(":l") and by[fid(k)].get("ir")) == N["quadrant.rank.films"],
               f"ranks.ladder/{vname}: number of IMDb films with a Letterboxd rank to link to is not quadrant.rank.films")
        if name == "directors.lean":
            cx, rows_v = v["w"] / 2, v["rows"]
            ok([r["t"] for r in rows_v] == lay["rows"], f"directors.lean/{vname}: row bands do not match the row order")
            band = {r["t"]: r for r in rows_v}
            for k, (x, y) in P.items():
                d = k[2:].split("|")[0]
                ok(band[d]["y0"] < y < band[d]["y1"], f"directors.lean/{vname}: {k} is not inside its director's row")
                ok((x < cx) == k.endswith(":i"), f"directors.lean/{vname}: {k} on the wrong side of the centre line")
            for r in rows_v:
                for s, side in (("i", "imdb"), ("l", "lb")):
                    sk = [k for k in ks if k.startswith(f"s:{r['t']}|") and k.endswith(":" + s)]
                    want = N[f"director.{r['key']}.{side}"]
                    ok(len(sk) == want, f"directors.lean/{vname}: {r['t']} {side} has {len(sk)} dots, numbers.json says {want}")
                    sh = [abs(P[k][0] - cx) for k in sk if by[fid(k)]["grp"] == "both"]
                    ot = [abs(P[k][0] - cx) for k in sk if by[fid(k)]["grp"] != "both"]
                    ok(not sh or not ot or max(sh) <= min(ot) + 1e-6, f"directors.lean/{vname}: {r['t']} {side}: a shared film is not next to the centre line")
            leans = [N[f"director.{r['key']}.lb"] - N[f"director.{r['key']}.imdb"] for r in rows_v]
            ok(leans == sorted(leans), f"directors.lean/{vname}: rows are not ordered from IMDb-leaning to Letterboxd-leaning")
        for l in v["deco"].get("labels", []):
            for ph in re.findall(r"\{([^}]+)\}", l["t"]):
                ok(ph in N, f"{name}/{vname}: label placeholder {{{ph}}} is not in numbers.json")
            fixed = re.sub(r"Top 250|out of 10", "", re.sub(r"\{[^}]+\}", "", l["t"]))  # list names and the rating scale, not data
            ok(not re.search(r"\d", fixed), f"{name}/{vname}: label '{l['t']}' types a number instead of a placeholder")

# ------------------------------------------------------------------ report
raw = (SITE / "films.json").stat().st_size + (SITE / "numbers.json").stat().st_size
for x in fails:
    print("FAIL", x)
print(f"\n{passes} passed, {len(fails)} failed | {len(films)} films, {len(N)} numbers, {len(S)} series, {raw // 1024} KB uncompressed")
sys.exit(1 if fails else 0)

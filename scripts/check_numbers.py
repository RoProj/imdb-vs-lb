"""Re-check every number the story relies on, straight from the data files.

Run:   python3 -I scripts/check_numbers.py            (prints every check; exit code 1 if anything fails)
       python3 -I scripts/check_numbers.py --quiet    (only failures and the summary)

Three kinds of check:
  1. SOURCE   the lists are complete and unchanged since scraping (raw IMDb file and Letterboxd list pages re-read here)
  2. NUMBER   each figure used in STORY_PLAN.md is recomputed from data/*.csv and compared with the value the plan states
  3. PLAN     the plan text still contains the wording that states that figure (so the document and the data cannot drift apart)

The calculations are written fresh here and do not import the pipeline scripts.
To add a claim: add a line using check(...) below. To refresh after new data: run, read the failures, fix the data or the plan.
"""
import csv, re, sys, statistics as st
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D, RAW = ROOT / "data", ROOT / "raw"
QUIET = "--quiet" in sys.argv
# the story plan is a working document kept out of the public repo; without it the wording checks are skipped,
# and every figure is still recomputed from the CSVs and compared with its expected value
PLAN_FILE = ROOT / "STORY_PLAN.md"
PLAN = PLAN_FILE.read_text(encoding="utf-8") if PLAN_FILE.exists() else None
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8", newline="")))

results = []  # (status, section, description, detail)
if PLAN is None:
    results.append(("INFO", "PLAN", "STORY_PLAN.md not present: plan wording checks skipped", ""))


def check(section, desc, actual, expected, snippet=None, tol=0.0):
    ok = abs(actual - expected) <= tol if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) else actual == expected
    results.append(("PASS" if ok else "FAIL", section, desc, f"data says {actual!r}, expected {expected!r}"))
    if snippet is not None and PLAN is not None:
        has = snippet in PLAN
        results.append(("PASS" if has else "FAIL", "PLAN", f"{desc}: wording present", f"looking for: {snippet}"))


def info(section, text):
    results.append(("INFO", section, text, ""))


pct = lambda n, d: int(n / d * 100 + 0.5)
mean2 = lambda xs: round(sum(xs) / len(xs), 2)


def fisher(a, n1, b, n2):
    k, n = a + b, n1 + n2
    p = lambda x: comb(n1, x) * comb(n2, k - x) / comb(n, k)
    p0 = p(a)
    return sum(p(x) for x in range(max(0, k - n2), min(n1, k) + 1) if p(x) <= p0 * (1 + 1e-9))


# ------------------------------------------------------------------ load
films = rd(D / "viz_films.csv")
uni = rd(D / "unified.csv")
gcred = {r["imdb_id"]: r for r in rd(D / "gender_credits.csv")}
L = {k: [r for r in films if r["list"] == k] for k in ("IMDb250", "LB250")}
ids = {k: {r["imdb_id"] for r in v} for k, v in L.items()}
distinct = {r["imdb_id"]: r for r in films}
IM, LB = "IMDb250", "LB250"

# ------------------------------------------------------------------ 1. SOURCE integrity
S = "SOURCE"
raw_imdb = rd(RAW / "imdb_top250_raw.csv")
check(S, "raw IMDb file has 250 rows", len(raw_imdb), 250)
check(S, "IMDb ranks are exactly 1 to 250", sorted(int(r["imdb_rank"]) for r in raw_imdb), list(range(1, 251)))
check(S, "IMDb ids are unique", len({r["imdb_id"] for r in raw_imdb}), 250)

# the saved Letterboxd list pages stay local (they're someone else's pages); without them these two checks are skipped
pages = [RAW / f"lb_list_{p}.html" for p in range(1, 6)]
if all(p.exists() for p in pages):
    slugs = []
    for p in pages:
        slugs += re.findall(r'data-item-slug="([^"]+)"', p.read_text(encoding="utf-8", errors="replace"))
    check(S, "Letterboxd list pages give 500 distinct films", len(set(slugs)), 500)
    lb_csv = rd(D / "letterboxd.csv")
    check(S, "data/letterboxd.csv keeps the list-page order", [r["lb_slug"] for r in lb_csv], slugs)
else:
    info(S, "saved Letterboxd list pages not present: list-page checks skipped")
lb500 = {r["imdb_id"]: r for r in uni if r["list"] == "LB500"}
bad_rank = [r["title"] for r in L[LB] if not (r["lb_rank250"] and r["imdb_id"] in lb500 and int(r["lb_rank250"]) == int(lb500[r["imdb_id"]]["rank"]) <= 250)]
check(S, "every Letterboxd-list row has a rank of 250 or better matching unified.csv", bad_rank, [])
imdb_rank_src = {r["imdb_id"]: int(r["imdb_rank"]) for r in raw_imdb}
check(S, "every IMDb-list row's rank matches the raw IMDb file", [r["title"] for r in L[IM] if int(r["imdb_rank"]) != imdb_rank_src[r["imdb_id"]]], [])
check(S, "Letterboxd rating on a 10-point scale is exactly double the 5-point rating",
      [r["title"] for r in films if abs(float(r["lb_rating_10"]) - 2 * float(r["lb_rating"])) > 0.011], [])
check(S, "each list has 250 rows and 250 distinct films", (len(L[IM]), len(ids[IM]), len(L[LB]), len(ids[LB])), (250, 250, 250, 250))
for col in ("title", "year", "directors", "genres", "country", "primary_language", "imdb_rating", "lb_rating", "runtime_min"):
    check(S, f"no empty {col}", sum(1 for r in films if not str(r[col]).strip()), 0)
check(S, "IMDb #1 is The Shawshank Redemption", next(r["title"] for r in L[IM] if r["imdb_rank"] == "1"), "The Shawshank Redemption")
check(S, "Letterboxd #1 is Harakiri", next(r["title"] for r in L[LB] if r["lb_rank250"] == "1"), "Harakiri")
info(S, f"Shawshank's Letterboxd rank is #{distinct['tt0111161']['lb_rank500'] or 'not in top 500'}; Harakiri's IMDb rank is #{distinct['tt0056058']['imdb_rank'] or 'not in top 250'}")

# ------------------------------------------------------------------ 2. NUMBERS: overlap
S = "OVERLAP"
both = ids[IM] & ids[LB]
check(S, "films on both lists", len(both), 111, "**111** films are on both lists")
check(S, "only on IMDb", len(ids[IM] - ids[LB]), 139, "**139** are only on IMDb and **139** only on Letterboxd")
check(S, "only on Letterboxd", len(ids[LB] - ids[IM]), 139)
check(S, "distinct films across both lists", len(distinct), 389, "**389** different films")
check(S, "IMDb-only films ranked 251 to 500 on Letterboxd", sum(1 for r in L[IM] if r["lb_rank500"] and int(r["lb_rank500"]) > 250), 60, "**60** sit just outside")
check(S, "IMDb films not in Letterboxd's top 500", sum(1 for r in L[IM] if not r["lb_rank500"]), 79, "**79** are not in Letterboxd's top 500")

# ------------------------------------------------------------------ country
S = "COUNTRY"
def cnt(lst, col, val): return sum(1 for r in L[lst] if r[col] == val)
check(S, "US films on IMDb list", cnt(IM, "country", "United States"), 145, "**58%** of IMDb's list (145 films)")
check(S, "US films on Letterboxd list", cnt(LB, "country", "United States"), 83, "**33%** of Letterboxd's (83 films)")
check(S, "Japan on IMDb / Letterboxd", (cnt(IM, "country", "Japan"), cnt(LB, "country", "Japan")), (19, 48), "**8%** against **19%**")
check(S, "UK on IMDb / Letterboxd", (cnt(IM, "country", "United Kingdom"), cnt(LB, "country", "United Kingdom")), (31, 15))
check(S, "countries represented", tuple(len({r["country"] for r in L[k]}) for k in (IM, LB)), (23, 33), "Letterboxd covers **33** countries, IMDb **23**")
def top3(lst):
    c = {}
    for r in L[lst]: c[r["country"]] = c.get(r["country"], 0) + 1
    return pct(sum(sorted(c.values(), reverse=True)[:3]), 250)
check(S, "share held by top three countries", (top3(IM), top3(LB)), (78, 59), "**78%** of IMDb's list but **59%**")
check(S, "films with more than one listed country (%)", tuple(pct(sum(1 for r in L[k] if ";" in r["countries"]), 250) for k in (IM, LB)), (39, 37))

# ------------------------------------------------------------------ year
S = "YEAR"
yrs = {k: [int(r["year"]) for r in L[k]] for k in L}
check(S, "median release year", (st.median(yrs[IM]), st.median(yrs[LB])), (1997.0, 1987.5), "median release year **1997** on IMDb, **1987.5** on Letterboxd")
check(S, "share from 2000 onwards (%)", tuple(pct(sum(y >= 2000 for y in yrs[k]), 250) for k in (IM, LB)), (44, 33), "**44%** of IMDb's films are from 2000 onwards against **33%**")
check(S, "share before 1970 (%)", tuple(pct(sum(y < 1970 for y in yrs[k]), 250) for k in (IM, LB)), (24, 34), "**24%** of IMDb's films are from before 1970 against **34%**")
dec = lambda k, d: sum(1 for y in yrs[k] if d <= y < d + 10)
check(S, "IMDb films in the 2000s / 2010s / 1990s", (dec(IM, 2000), dec(IM, 2010), dec(IM, 1990)), (48, 44, 39))
check(S, "Letterboxd films in the 1960s / 1990s / 2000s / 1950s", (dec(LB, 1960), dec(LB, 1990), dec(LB, 2000), dec(LB, 1950)), (36, 37, 36, 33))
check(S, "2020s films, Letterboxd vs IMDb", (dec(LB, 2020), dec(IM, 2020)), (24, 18), "Letterboxd has *more* 2020s films than IMDb (24 against 18)")

# ------------------------------------------------------------------ runtime
S = "RUNTIME"
rt = {k: [int(r["runtime_min"]) for r in L[k]] for k in L}
check(S, "median runtime (minutes)", (st.median(rt[IM]), st.median(rt[LB])), (129, 125), "median **129** minutes on IMDb and **125** on Letterboxd")
check(S, "mean runtime (minutes)", (round(st.mean(rt[IM])), round(st.mean(rt[LB]))), (132, 131))
check(S, "films of 2 hours or more (%)", tuple(pct(sum(x >= 120 for x in rt[k]), 250) for k in (IM, LB)), (62, 61), "**62%** of IMDb's films and **61%** of Letterboxd's")
check(S, "films of 3 hours or more", tuple(sum(x >= 180 for x in rt[k]) for k in (IM, LB)), (17, 20), "**17** IMDb films and **20** Letterboxd films run three hours or longer")
check(S, "films under 90 minutes", tuple(sum(x < 90 for x in rt[k]) for k in (IM, LB)), (17, 20))
check(S, "longest film and shortest film", (max(rt[LB]), min(rt[IM]), min(rt[LB])), (432, 45, 45), "*Satantango* 432 min")

# ------------------------------------------------------------------ language and genre
S = "LANGUAGE"
lang = lambda k, v: sum(1 for r in L[k] if r["primary_language"] == v)
check(S, "English as main language", (lang(IM, "English"), lang(LB, "English")), (187, 110))
check(S, "Japanese as main language", (lang(IM, "Japanese"), lang(LB, "Japanese")), (19, 47))
check(S, "French as main language", (lang(IM, "French"), lang(LB, "French")), (5, 15))
check(S, "silent films on IMDb's list", sum(int(r["is_silent"]) for r in L[IM]), 6)
S = "GENRE"
gen = lambda k, g: sum(1 for r in L[k] if g in [x.strip() for x in r["genres"].split(";")])
for g, exp in {"Drama": (74, 89), "Adventure": (26, 14), "Action": (17, 8), "Sci-Fi": (13, 8), "Crime": (22, 16), "Romance": (10, 15)}.items():
    check(S, f"{g} share (%)", (pct(gen(IM, g), 250), pct(gen(LB, g), 250)), exp)
if PLAN is not None: results.append(("PASS" if "**74%** of IMDb's films and **89%** of Letterboxd's" in PLAN else "FAIL", "PLAN", "Drama wording present", ""))

# ------------------------------------------------------------------ directors
S = "DIRECTORS"
dl = lambda r: [d.strip() for d in r["directors"].split(";") if d.strip()]
dc = {k: {} for k in L}
for k in L:
    for r in L[k]:
        for d in dl(r): dc[k][d] = dc[k].get(d, 0) + 1
Di, Dl = set(dc[IM]), set(dc[LB])
check(S, "distinct directors", (len(Di), len(Dl)), (181, 176), "**181** different directors")
check(S, "directors on both / only IMDb / only Letterboxd", (len(Di & Dl), len(Di - Dl), len(Dl - Di)), (84, 97, 92), "**84** are on both lists")
check(S, "one-film directors among the only-IMDb / only-Letterboxd groups", (sum(dc[IM][d] == 1 for d in Di - Dl), sum(dc[LB][d] == 1 for d in Dl - Di)), (84, 70), "(84 of 97 on IMDb, 70 of 92 on Letterboxd)")
def with_min(k, m): return {d for d, n in dc[k].items() if n >= m}
share = lambda k, m: pct(sum(1 for r in L[k] if any(d in with_min(k, m) for d in dl(r))), 250)
check(S, "films by directors with 2+ films on that list (%)", (share(IM, 2), share(LB, 2)), (56, 59), "**56%** of IMDb's films and **59%** of Letterboxd's")
check(S, "directors with 3+ films", (len(with_min(IM, 3)), len(with_min(LB, 3))), (23, 21))
check(S, "directors with 2+ films on BOTH lists", sum(1 for d in Di & Dl if dc[IM][d] >= 2 and dc[LB][d] >= 2), 22)
pair = lambda d: (dc[IM].get(d, 0), dc[LB].get(d, 0))
check(S, "Nolan / Kurosawa / Tarkovsky / Bergman (IMDb, Letterboxd)", (pair("Christopher Nolan"), pair("Akira Kurosawa"), pair("Andrei Tarkovsky"), pair("Ingmar Bergman")), ((9, 5), (6, 9), (0, 5), (2, 6)))
fl = {k: {} for k in L}
for k in L:
    for r in L[k]:
        for d in dl(r): fl[k].setdefault(d, set()).add(r["imdb_id"])
check(S, "shared directors with no film in common", sorted(d for d in Di & Dl if not (fl[IM][d] & fl[LB][d])), ["Wes Anderson", "William Friedkin"])
check(S, "films by directors on both lists (%)", (pct(sum(1 for r in L[IM] if any(d in Di & Dl for d in dl(r))), 250), pct(sum(1 for r in L[LB] if any(d in Di & Dl for d in dl(r))), 250)), (64, 56))

# ------------------------------------------------------------------ gender: directors
S = "GENDER: DIRECTORS"
wf = {k: sum(int(r["has_woman_director"]) for r in L[k]) for k in L}
check(S, "films with a woman director", (wf[IM], wf[LB]), (4, 7), "**4 of 250 (1.6%)** on IMDb, **7 of 250 (2.8%)** on Letterboxd")
check(S, "distinct films with a woman director", len({r["imdb_id"] for r in films if int(r["has_woman_director"])}), 10)
cw = {k: (sum(int(r["directors_women"]) for r in L[k]), sum(int(r["directors_men"]) for r in L[k])) for k in L}
check(S, "director credits (women, men)", (cw[IM], cw[LB]), ((5, 276), (7, 263)))
mx = next(r for r in films if r["title"] == "The Matrix")
check(S, "The Matrix's two directors are counted as women, none as men", (mx["directors_women"], mx["directors_men"]), ("2", "0"), "trans women are counted as women everywhere")
check(S, "directors' gender-count mismatches with IMDb credits", sum(1 for r in {x["imdb_id"]: x for x in films}.values() if r["gender_check"] == "count_differs"), 12)
p1 = fisher(wf[IM], 250, wf[LB], 250)
check(S, "p-value, films with a woman director (about 0.54)", round(p1, 2), 0.54, tol=0.02)
p2 = fisher(cw[IM][0], sum(cw[IM]), cw[LB][0], sum(cw[LB]))
check(S, "p-value, women among director credits (about 0.57)", round(p2, 2), 0.57, tol=0.02)

# ------------------------------------------------------------------ gender: on screen and crew
S = "GENDER: SCREEN AND CREW"
g = lambda k: [gcred[r["imdb_id"]] for r in L[k] if r["imdb_id"] in gcred]
lead = {k: [int(x["lead_is_woman"]) for x in g(k) if x["lead_is_woman"] != ""] for k in L}
check(S, "first-billed performer is a woman (count, films)", ((sum(lead[IM]), len(lead[IM])), (sum(lead[LB]), len(lead[LB]))), ((24, 249), (59, 250)), "24 of 249 IMDb films (9.6%)")
if PLAN is not None: results.append(("PASS" if "59 of 250 Letterboxd films (23.6%)" in PLAN else "FAIL", "PLAN", "lead figure for Letterboxd present", ""))
check(S, "top-3 billed women / total", (tuple((sum(int(x["top3_women"]) for x in g(k)), sum(int(x["top3_n"]) for x in g(k))) for k in (IM, LB))), ((191, 747), (245, 748)))
check(S, "films with no woman in top 3 / with 2+", (tuple(sum(int(x["top3_women"]) == 0 for x in g(k)) for k in (IM, LB)), tuple(sum(int(x["top3_women"]) >= 2 for x in g(k)) for k in (IM, LB))), ((91, 73), (31, 61)))
check(S, "p-value, lead performer gap (below 0.001)", fisher(sum(lead[IM]), len(lead[IM]), sum(lead[LB]), len(lead[LB])) < 0.001, True)
def role(k, r_):
    return (sum(int(x[f"{r_}_women"]) for x in g(k)), sum(int(x[f"{r_}_men"]) for x in g(k)))
expected_roles = {"writer": ((49, 510), (40, 482)), "producer": ((70, 341), (50, 303)), "editor": ((50, 245), (53, 199)),
                  "cinematographer": ((4, 235), (7, 238)), "composer": ((11, 237), (5, 220)), "production_designer": ((20, 148), (26, 123))}
for r_, exp in expected_roles.items():
    check(S, f"{r_}: women and men credits (IMDb, Letterboxd)", (role(IM, r_), role(LB, r_)), exp)

# ------------------------------------------------------------------ ratings, ranks, quadrants
S = "RATINGS AND RANKS"
mi = lambda k: mean2([float(r["imdb_rating"]) for r in L[k]])
ml = lambda k: mean2([float(r["lb_rating_10"]) for r in L[k]])
check(S, "average IMDb rating of each list's films", (mi(IM), mi(LB)), (8.31, 8.18))
check(S, "average Letterboxd rating (out of 10) of each list's films", (ml(IM), ml(LB)), (8.47, 8.71))
q = {"Popular on both": 0, "Popular on Letterboxd": 0, "Popular on IMDb": 0, "Last on both": 0}
pool = [r for r in L[IM] if r["lb_rank500"]]
for r in pool:
    x, y = int(r["imdb_rank"]), int(r["lb_rank500"])
    q["Popular on both" if x <= 125 and y <= 250 else "Popular on Letterboxd" if x > 125 and y <= 250 else "Popular on IMDb" if x <= 125 else "Last on both"] += 1
check(S, "rank quadrants (171 films): both / Letterboxd / IMDb / last", (len(pool), tuple(q.values())), (171, (73, 38, 28, 32)))
mi_, ml_ = st.median(float(r["imdb_rating"]) for r in distinct.values()), st.median(float(r["lb_rating_10"]) for r in distinct.values())
check(S, "median ratings across all 389 films (IMDb, Letterboxd out of 10)", (mi_, ml_), (8.2, 8.56), tol=0.005)
rq = [0, 0, 0, 0]
for r in distinct.values():
    hl, hi = float(r["lb_rating_10"]) >= ml_, float(r["imdb_rating"]) >= mi_
    rq[0 if hl and hi else 1 if hi else 2 if hl else 3] += 1
check(S, "rating quadrants: high on both / IMDb higher / Letterboxd higher / low on both", tuple(rq), (111, 96, 91, 91))
for t, a, b in [("Inception", 13, 248), ("Alien", 51, 246), ("The Battle of Algiers", 244, 28), ("La haine", 226, 20), ("The Passion of Joan of Arc", 249, 54)]:
    r = distinct[next(i for i, x in distinct.items() if x["title"] == t)]
    check(S, f"{t}: IMDb rank, Letterboxd rank", (int(r["imdb_rank"]), int(r["lb_rank500"])), (a, b))

# ------------------------------------------------------------------ report
fails = [r for r in results if r[0] == "FAIL"]
if not QUIET:
    for st_, sec, desc, det in results:
        print(f"{st_:4s} [{sec}] {desc}" + (f"  ({det})" if st_ == "FAIL" or st_ == "INFO" and det else ""))
else:
    for st_, sec, desc, det in fails + [r for r in results if r[0] == "INFO"]:
        print(f"{st_:4s} [{sec}] {desc}  ({det})")
n_pass = sum(1 for r in results if r[0] == "PASS")
print(f"\n{n_pass} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)

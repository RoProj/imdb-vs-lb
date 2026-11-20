"""Gender of key credits for every film in both lists.

Inputs : raw/imdb_principals_subset.tsv  (IMDb title.principals rows for our 389 films; IMDb's own "principal" credits:
         top-billed cast and key crew, at most 10 per film)
         data/viz_films.csv              (which film is on which list)
Gender : performers  -> IMDb credit category: "actress" = woman, "actor" = man (binary, taken from how IMDb lists the credit)
         crew        -> Wikidata P21 for the person, looked up by IMDb person id (P345); cached in raw/wikidata_person_gender.json
         women = "female" or "trans woman"; men = "male" or "trans man"; anything else or no Wikidata item = unknown
Outputs: data/gender_credits.csv (one row per film), summary printed.
"""
import csv, json, subprocess, time, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, D = ROOT / "raw", ROOT / "data"
CREW = ["director", "writer", "producer", "editor", "cinematographer", "composer", "production_designer", "casting_director"]
WOMEN, MEN = {"female", "trans woman"}, {"male", "trans man"}

principals = list(csv.DictReader(open(RAW / "imdb_principals_subset.tsv", encoding="utf-8"), delimiter="\t"))
people = sorted({r["nconst"] for r in principals if r["category"] in CREW})

cache_path = RAW / "wikidata_person_gender.json"
cache = json.load(open(cache_path)) if cache_path.exists() else {}
todo = [p for p in people if p not in cache]
print(len(people), "crew people;", len(todo), "to look up")
UA = "film-comparison-research/0.1 (personal data-viz project)"
for i in range(0, len(todo), 250):
    batch = todo[i:i + 250]
    q = ('SELECT ?imdbp ?gLabel WHERE { VALUES ?imdbp { ' + " ".join(f'"{x}"' for x in batch) +
         ' } ?p wdt:P345 ?imdbp . OPTIONAL { ?p wdt:P21 ?g . } SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')
    qf = RAW / "_q.rq"; qf.write_text(q)
    r = subprocess.run(["curl", "-sS", "--http1.1", "-m", "90", "-X", "POST", "https://query.wikidata.org/sparql",
                        "-H", "Accept: application/sparql-results+json", "-H", f"User-Agent: {UA}",
                        "--data-urlencode", f"query@{qf}"], capture_output=True)
    try:
        res = json.loads(r.stdout)["results"]["bindings"]
    except Exception as e:
        print("batch failed", i, e, r.stderr[:100]); time.sleep(5); continue
    found = collections.defaultdict(set)
    for b in res:
        found[b["imdbp"]["value"]].add(b.get("gLabel", {}).get("value", ""))
    for p in batch:
        cache[p] = sorted(found.get(p, set()) - {""}) if p in found else None   # None = no Wikidata item
    json.dump(cache, open(cache_path, "w"))
    print("batch", i // 250 + 1, "done", flush=True)
    time.sleep(2)


def gender_of(n):
    g = cache.get(n)
    if not g: return "unknown"
    if any(x in WOMEN for x in g): return "woman"
    if any(x in MEN for x in g): return "man"
    return "unknown"


by_film = collections.defaultdict(list)
for r in principals:
    by_film[r["tconst"]].append(r)
for v in by_film.values():
    v.sort(key=lambda r: int(r["ordering"]))

out = []
for t, rows in by_film.items():
    perf = [r for r in rows if r["category"] in ("actor", "actress")]
    rec = {"imdb_id": t,
           "lead_is_woman": int(perf[0]["category"] == "actress") if perf else "",
           "top3_women": sum(r["category"] == "actress" for r in perf[:3]),
           "top3_n": len(perf[:3]),
           "performers_women": sum(r["category"] == "actress" for r in perf), "performers_n": len(perf)}
    for c in CREW:
        g = [gender_of(r["nconst"]) for r in rows if r["category"] == c]
        rec[f"{c}_women"], rec[f"{c}_men"], rec[f"{c}_unknown"] = g.count("woman"), g.count("man"), g.count("unknown")
    out.append(rec)
with open(D / "gender_credits.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

lists = collections.defaultdict(set)
for r in csv.DictReader(open(D / "viz_films.csv", encoding="utf-8")):
    lists[r["list"]].add(r["imdb_id"])
rec = {r["imdb_id"]: r for r in out}
print("\nfilms with principals:", len(rec))
for lst in ("IMDb250", "LB250"):
    ids = [i for i in lists[lst] if i in rec]
    n = len(ids)
    leads = [rec[i]["lead_is_woman"] for i in ids if rec[i]["lead_is_woman"] != ""]
    t3w = sum(rec[i]["top3_women"] for i in ids); t3n = sum(rec[i]["top3_n"] for i in ids)
    pw = sum(rec[i]["performers_women"] for i in ids); pn = sum(rec[i]["performers_n"] for i in ids)
    print(f"\n== {lst} ({n} films)")
    print(f"  first-billed performer is a woman: {sum(leads)}/{len(leads)} ({sum(leads)/len(leads)*100:.0f}%)")
    print(f"  top-3 billed performers who are women: {t3w}/{t3n} ({t3w/t3n*100:.0f}%) | all billed performers: {pw}/{pn} ({pw/pn*100:.0f}%)")
    print(f"  films with 0 women among top 3 billed: {sum(1 for i in ids if rec[i]['top3_women']==0)} | films with 2+ women in top 3: {sum(1 for i in ids if rec[i]['top3_women']>=2)}")
    for c in CREW:
        W = sum(rec[i][f"{c}_women"] for i in ids); M = sum(rec[i][f"{c}_men"] for i in ids); U = sum(rec[i][f"{c}_unknown"] for i in ids)
        films_w = sum(1 for i in ids if rec[i][f"{c}_women"] > 0)
        if W + M:
            print(f"  {c:20s} women {W:3d} men {M:4d} unknown {U:3d} -> {W/(W+M)*100:4.1f}% women among known | films with a woman in this role: {films_w}")

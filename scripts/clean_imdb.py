"""raw/imdb_top250_raw.csv -> data/imdb_top250.csv (+ sanity checks)."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "raw" / "imdb_top250_raw.csv", newline="", encoding="utf-8")))

for r in rows:
    langs = [l for l in r["languages"].split("; ") if l]
    silent = bool(langs) and langs[0] == "None"
    # IMDb lists "None" for silent films (intertitles in another language follow it)
    r["is_silent"] = "1" if silent else "0"
    real = [l for l in langs if l != "None"]
    r["languages"] = "; ".join(real)
    r["primary_language"] = real[0] if real else ("None (silent)" if silent else "")
    r["countries_n"] = str(len([c for c in r["countries"].split("; ") if c]))
    r["primary_country"] = r["countries"].split("; ")[0]
    r["imdb_rank"] = int(r["imdb_rank"])
    r["year"] = int(r["year"])

assert len(rows) == 250
assert sorted(r["imdb_rank"] for r in rows) == list(range(1, 251))
assert len({r["imdb_id"] for r in rows}) == 250
for col in ["title", "year", "directors", "genres", "countries", "primary_language", "imdb_rating"]:
    missing = [r["imdb_rank"] for r in rows if not str(r[col]).strip()]
    print(f"{col:18s} missing: {missing}")

cols = ["imdb_rank", "imdb_id", "title", "year", "directors", "genres", "countries", "primary_country",
        "primary_language", "languages", "is_silent", "imdb_rating", "imdb_votes"]
(ROOT / "data").mkdir(exist_ok=True)
with open(ROOT / "data" / "imdb_top250.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: r["imdb_rank"]))
print("wrote", len(rows), "rows; silent films:", sum(r["is_silent"] == "1" for r in rows))

"""data/unified.csv -> data/comparison_250.csv (IMDb Top 250 + Letterboxd Top 250 only).
Run order: unify.py -> main_country.py -> make_250.py"""
import csv
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "data"
rows = list(csv.DictReader(open(D / "unified.csv", encoding="utf-8")))
keep = []
for r in rows:
    if r["list"] == "IMDb250":
        keep.append(r)
    elif r["list"] == "LB500" and int(r["rank"]) <= 250:
        r["list"] = "LB250"
        keep.append(r)
with open(D / "comparison_250.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(keep[0]))
    w.writeheader()
    w.writerows(keep)
print("wrote", len(keep), "rows")

# ---- canonical country: IMDb's first-listed country (historical names -> today's country) ----
MODERN = {"West Germany": "Germany", "Soviet Union": "Russia", "Czechoslovakia": "Czech Republic", "Yugoslavia": "Serbia"}
rows = list(csv.DictReader(open(D / "comparison_250.csv", encoding="utf-8")))
for r in rows:
    first = r["countries"].split("; ")[0]
    r["country"] = MODERN.get(first, first)
fields = list(rows[0])
with open(D / "comparison_250.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
from collections import Counter
for nm in ("IMDb250", "LB250"):
    sub = [r for r in rows if r["list"] == nm]
    print(nm, ", ".join(f"{k} {v} ({v/len(sub):.0%})" for k, v in Counter(r["country"] for r in sub).most_common(6)))

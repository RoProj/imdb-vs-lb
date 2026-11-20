"""Precompute dot positions for every dot chart: data/site/layouts.json.

Run after export_site_data.py:   python3 -I scripts/build_layouts.py
The gate (check_export.py) then checks the layouts: right films, inside the frame, no overlapping dots,
and positions that match the data value they encode (a dot at year 1994 sits at 1994 on the axis).

Each layout has `keys` (one per dot) and two variants: `wide` (reference width 960 px) and `narrow` (360 px, phones).
A variant holds w, h, r (dot radius), xy (flat list x0,y0,x1,y1,...) and deco (axis ticks, lines, labels).
Labels never contain data numbers; they may hold {placeholders} that the page fills from numbers.json.

Dot keys:  tt0111161:i  the film as an entry on IMDb's list      tt0111161:l  ... on Letterboxd's list
           tt0111161    the film itself                          d:Name       a director
           s:Name|tt0111161  a film on a director's filmography strip
"""
import json, math, hashlib
from pathlib import Path
import re as _re, unicodedata as _ud
def dslug(name):
    """number-key slug for a director: 'Hirokazu Koreeda' -> 'hirokazu_koreeda'"""
    return _re.sub(r"[^a-z0-9]+", "_", _ud.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("_")

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "data" / "site"
films = [f for f in json.load(open(SITE / "films.json", encoding="utf-8"))["films"] if f["grp"] != "lb500"]
by = {f["id"]: f for f in films}
IMf = sorted([f for f in films if "ir" in f], key=lambda f: f["ir"])
LBf = sorted([f for f in films if f.get("lr", 999) <= 250], key=lambda f: f["lr"])
W = {"wide": 960, "narrow": 360}
NUM = json.load(open(SITE / "numbers.json", encoding="utf-8"))["n"]
R2 = lambda v: round(v, 1)


def variant(w, h, r, pts, deco, keys):
    xy = []
    for k in keys:
        x, y = pts[k]
        xy += [R2(x), R2(y)]
    return {"w": w, "h": math.ceil(h), "r": r, "xy": xy, "deco": deco}


def dodge(items, r, side, pad=0.6, start=0.0, placed=None):
    """items: list of (key, x). Returns {key: offset}; side 'up' (<= -start), 'down' (>= start) or 'both'.
    placed: dots already on the row as (x, offset), which new dots must avoid (and which are extended in place)."""
    placed = [] if placed is None else placed
    out, d = {}, 2 * r + pad
    for key, x in sorted(items, key=lambda t: t[1]):
        forb = []
        for px, py in placed:
            dx = abs(px - x)
            if dx < d:
                h = math.sqrt(d * d - dx * dx)
                forb.append((py - h, py + h))
        base = {"both": 0.0, "up": -start, "down": start}[side]
        cands = [base] + [a for a, b in forb] + [b for a, b in forb]
        cands = [c for c in cands if (side == "both" or (side == "up" and c <= -start + 1e-9) or (side == "down" and c >= start - 1e-9))]
        free = [c for c in cands if all(not (a + 1e-6 < c < b - 1e-6) for a, b in forb)]
        y = min(free, key=lambda c: (abs(c), c))
        placed.append((x, y))
        out[key] = y
    return out


def grid(keys, cols, x0, y0, step):
    return {k: (x0 + (i % cols) * step, y0 + (i // cols) * step) for i, k in enumerate(keys)}


L = {}

# ------------------------------------------------------------------ ladder (hero, meet the lists, slope chart)
keys = [f"{f['id']}:i" for f in IMf] + [f"{f['id']}:l" for f in LBf]
L["ladder"] = {"keys": keys, "shape": "circle"}
for v, w in W.items():
    top, step, r = 44, 2.4, 1.9 if v == "wide" else 1.6
    xi, xl = (w * 0.34, w * 0.66) if v == "wide" else (w * 0.28, w * 0.72)
    pts = {f"{f['id']}:i": (xi, top + (f["ir"] - 1) * step) for f in IMf}
    pts.update({f"{f['id']}:l": (xl, top + (f["lr"] - 1) * step) for f in LBf})
    deco = {"labels": [{"t": "IMDb", "x": xi, "y": 22, "a": "middle", "c": "head imdb"}, {"t": "Letterboxd", "x": xl, "y": 22, "a": "middle", "c": "head lb"}],
            "yticks": [{"v": str(n), "y": top + (n - 1) * step, "x": xi - 14} for n in (1, 50, 100, 150, 200, 250)]}
    L["ladder"][v] = variant(w, top + 250 * step + 16, r, pts, deco, keys)

# ------------------------------------------------------------------ overlap: two lists -> three groups
L["overlap.lists"] = {"keys": keys, "shape": "circle"}
L["overlap.groups"] = {"keys": keys, "shape": "circle"}
only_i = [f"{f['id']}:i" for f in IMf if f["grp"] == "imdb"]
only_l = [f"{f['id']}:l" for f in LBf if f["grp"] == "lb"]
shared = [f["id"] for f in IMf if f["grp"] == "both"]
order_i = [f"{f['id']}:i" for f in sorted(IMf, key=lambda f: (f["grp"] != "both", f["ir"]))]
order_l = [f"{f['id']}:l" for f in sorted(LBf, key=lambda f: (f["grp"] != "both", f["lr"]))]
for v, w in W.items():
    step, r = (14, 5.2) if v == "wide" else (11.5, 4.2)
    if v == "wide":
        bw = 24 * step
        gx = (w - 2 * bw) / 3
        a = grid(order_i, 25, gx, 50, step)
        b = grid(order_l, 25, 2 * gx + bw, 50, step)
        labs = [{"t": "IMDb Top 250", "x": gx + bw / 2, "y": 28, "a": "middle", "c": "head imdb"},
                {"t": "Letterboxd Top 250", "x": 2 * gx + bw + bw / 2, "y": 28, "a": "middle", "c": "head lb"}]
        h = 50 + 10 * step + 10
    else:
        bw = 24 * step
        x0 = (w - bw) / 2
        a = grid(order_i, 25, x0, 44, step)
        b = grid(order_l, 25, x0, 44 + 10 * step + 50, step)
        labs = [{"t": "IMDb Top 250", "x": w / 2, "y": 26, "a": "middle", "c": "head imdb"},
                {"t": "Letterboxd Top 250", "x": w / 2, "y": 44 + 10 * step + 26, "a": "middle", "c": "head lb"}]
        h = 44 + 20 * step + 60
    L["overlap.lists"][v] = variant(w, h, r, {**a, **b}, {"labels": labs}, keys)
    cols = 12 if v == "wide" else 9
    bw = (cols - 1) * step
    gap = (w - 3 * bw) / 4
    xs = [gap, 2 * gap + bw, 3 * gap + 2 * bw]
    pts = {}
    g0 = 96
    pts.update(grid(only_i, cols, xs[0], g0, step))
    sp = grid(shared, cols, xs[1], g0, step)
    for i in shared:
        pts[f"{i}:i"] = pts[f"{i}:l"] = sp[i]
    pts.update(grid(only_l, cols, xs[2], g0, step))
    rows = max(math.ceil(len(only_i) / cols), math.ceil(len(only_l) / cols), math.ceil(len(shared) / cols))
    labs = [{"t": "Only IMDb", "x": xs[0] + bw / 2, "y": 24, "a": "middle", "c": "head imdb"},
            {"t": "On both", "x": xs[1] + bw / 2, "y": 24, "a": "middle", "c": "head both"},
            {"t": "Only Letterboxd", "x": xs[2] + bw / 2, "y": 24, "a": "middle", "c": "head lb"},
            {"t": "{overlap.imdb_only}", "x": xs[0] + bw / 2, "y": 66, "a": "middle", "c": "big imdb"},
            {"t": "{overlap.both}", "x": xs[1] + bw / 2, "y": 66, "a": "middle", "c": "big both"},
            {"t": "{overlap.lb_only}", "x": xs[2] + bw / 2, "y": 66, "a": "middle", "c": "big lb"}]
    L["overlap.groups"][v] = variant(w, g0 + rows * step + 10, r, pts, {"labels": labs}, keys)

# ------------------------------------------------------------------ country rows (IMDb dots to the left, Letterboxd to the right)
tot = {}
for f in IMf + LBf:
    tot[f["c"]] = tot.get(f["c"], 0) + 1
top10 = sorted(tot, key=lambda c: (-tot[c], c))[:10]
rowname = lambda c: c if c in top10 else "Other countries"
order = top10 + ["Other countries"]
L["country.rows"] = {"keys": keys, "shape": "circle"}
for v, w in W.items():
    if v == "wide":
        step, r, high, mid, top = 10, 4.0, 5, 150, 50
    else:
        step, r, high, mid, top = 6, 2.3, 8, 112, 44
    rowh = high * step + (14 if v == "wide" else 12)
    pts, labs = {}, [{"t": "IMDb", "x": w / 2 - mid / 2 - 6, "y": 22, "a": "end", "c": "head imdb"},
                     {"t": "Letterboxd", "x": w / 2 + mid / 2 + 6, "y": 22, "a": "start", "c": "head lb"}]
    for ri, c in enumerate(order):
        y0 = top + ri * rowh
        for side, lst, sgn in (("i", IMf, -1), ("l", LBf, 1)):
            ent = [f for f in lst if rowname(f["c"]) == c]
            ent.sort(key=lambda f: (f["grp"] != "both", f["ir"] if side == "i" else f["lr"]))
            for j, f in enumerate(ent):
                col, row = j // high, j % high
                pts[f"{f['id']}:{side}"] = (w / 2 + sgn * (mid / 2 + r + 4 + col * step), y0 + row * step)
        labs.append({"t": c, "x": w / 2, "y": y0 + (high - 1) * step / 2 + 4, "a": "middle", "c": "row"})
    L["country.rows"][v] = variant(w, top + len(order) * rowh, r, pts, {"labels": labs}, keys)

# ------------------------------------------------------------------ country lean (scrollytelling): a centre line, IMDb grows left,
# Letterboxd grows right, films on both lists hug the line. Rows run from the most IMDb-leaning country to the most Letterboxd-leaning.
# Each named country has number keys country.<key>.{imdb,lb}.n; everything else is "Other countries" (country.rest).
LEAN_NAMES = {"United States": "us", "Japan": "japan", "United Kingdom": "uk", "Italy": "italy", "France": "france", "India": "india",
              "Germany": "germany", "Russia": "russia", "Iran": "iran", "Sweden": "sweden", "South Korea": "korea"}
cnt = lambda lst, c: sum(1 for f in lst if (f["c"] if f["c"] in LEAN_NAMES else "Other countries") == c)
lean_order = sorted(LEAN_NAMES, key=lambda c: (cnt(LBf, c) - cnt(IMf, c), -(cnt(LBf, c) + cnt(IMf, c)), c)) + ["Other countries"]
L["country.lean"] = {"keys": keys, "shape": "circle", "rows": lean_order,
                     "rowkeys": [LEAN_NAMES.get(c, "rest") for c in lean_order]}
for v, w in W.items():
    # wide screens: long, shallow rows (4 deep) that stretch across the screen, so a big country's row is visibly longer
    step, r, high, gap, top = (10, 4.0, 4, 6, 40) if v == "wide" else (7.4, 3.0, 10, 5, 38)
    rowh = 26 + high * step + 16
    cx = w / 2
    pts, rows = {}, []
    labs = [{"t": "IMDb", "x": cx - 14, "y": 16, "a": "end", "c": "head imdb"}, {"t": "Letterboxd", "x": cx + 14, "y": 16, "a": "start", "c": "head lb"}]
    for ri, c in enumerate(lean_order):
        y0 = top + ri * rowh
        by0 = y0 + 26 + r
        key = LEAN_NAMES.get(c, "rest")
        labs.append({"t": c, "x": cx, "y": y0 + 15, "a": "middle", "c": "row"})
        for side, lst, sgn, nm in (("i", IMf, -1, "imdb"), ("l", LBf, 1, "lb")):
            ent = [f for f in lst if (f["c"] if f["c"] in LEAN_NAMES else "Other countries") == c]
            ent.sort(key=lambda f: (f["grp"] != "both", f["ir"] if side == "i" else f["lr"]))
            for j, f in enumerate(ent):
                pts[f"{f['id']}:{side}"] = (cx + sgn * (gap + r + (j // high) * step), by0 + (j % high) * step)
            ncol = max(1, math.ceil(len(ent) / high))
            edge = gap + r + (ncol - 1) * step + r + 7
            labs.append({"t": "{country." + key + "." + nm + ".n}", "x": cx + sgn * edge, "y": by0 + (high - 1) * step / 2,
                         "a": "end" if sgn < 0 else "start", "c": f"count {nm}"})
        rows.append({"t": c, "key": key, "y0": y0, "y1": y0 + rowh})
    h = top + len(lean_order) * rowh + 6
    var = variant(w, h, r, pts, {"labels": labs, "lines": [{"x1": cx, "y1": top - 6, "x2": cx, "y2": h - 10, "c": "spine"}]}, keys)
    var["rows"] = rows
    L["country.lean"][v] = var

# ------------------------------------------------------------------ directors lean (scrollytelling): same structure as country.lean.
# One row per director with at least 4 films on either list; each film is one dot in a single line, IMDb's growing left
# of the centre line and Letterboxd's right, films on both lists next to the line. Rows run from IMDb-leaning to Letterboxd-leaning.
# Dot key: s:Director|tt0000000:i (a film on a director's row, as an entry on IMDb's list) or ...:l
dfilms = {}
for side, lst in (("i", IMf), ("l", LBf)):
    for f in lst:
        for d in f["d"]:
            dfilms.setdefault(d, {"i": [], "l": []})[side].append(f)
lean_dirs = [d for d, s_ in dfilms.items() if max(len(s_["i"]), len(s_["l"])) >= 4]
lean_dirs.sort(key=lambda d: (len(dfilms[d]["l"]) - len(dfilms[d]["i"]), -(len(dfilms[d]["l"]) + len(dfilms[d]["i"])), d))
dl_keys = [f"s:{d}|{f['id']}:{side}" for d in lean_dirs for side in "il" for f in dfilms[d][side]]
L["directors.lean"] = {"keys": dl_keys, "shape": "circle", "rows": lean_dirs, "rowkeys": [dslug(d) for d in lean_dirs]}
for v, w in W.items():
    # wide screens: bigger dots and spacing, so the short director rows still carry weight on a full-width chart
    step, r, gap, top = (19, 7.5, 9, 40) if v == "wide" else (11, 4.4, 6, 38)
    rowh = 24 + 2 * r + 14
    cx = w / 2
    pts, rows = {}, []
    labs = [{"t": "IMDb", "x": cx - 14, "y": 16, "a": "end", "c": "head imdb"}, {"t": "Letterboxd", "x": cx + 14, "y": 16, "a": "start", "c": "head lb"}]
    for ri, d in enumerate(lean_dirs):
        y0 = top + ri * rowh
        by0 = y0 + 24 + r
        labs.append({"t": d, "x": cx, "y": y0 + 15, "a": "middle", "c": "row"})
        for side, sgn, nm in (("i", -1, "imdb"), ("l", 1, "lb")):
            ent = sorted(dfilms[d][side], key=lambda f: (f["grp"] != "both", f["ir"] if side == "i" else f["lr"]))
            for j, f in enumerate(ent):
                pts[f"s:{d}|{f['id']}:{side}"] = (cx + sgn * (gap + r + j * step), by0)
            edge = gap + r + max(0, len(ent) - 1) * step + r + 8
            labs.append({"t": "{director." + dslug(d) + "." + nm + "}", "x": cx + sgn * edge, "y": by0,
                         "a": "end" if sgn < 0 else "start", "c": f"count {nm}"})
        rows.append({"t": d, "key": dslug(d), "y0": y0, "y1": y0 + rowh})
    h = top + len(lean_dirs) * rowh + 6
    var = variant(w, h, r, pts, {"labels": labs, "lines": [{"x1": cx, "y1": top - 6, "x2": cx, "y2": h - 10, "c": "spine"}]}, dl_keys)
    var["rows"] = rows
    L["directors.lean"][v] = var

# ------------------------------------------------------------------ women directors grid (scrollytelling): each list as a block of 250
# dots either side of the centre line, filled row by row from the top, starting next to the line. Films a woman directed or
# co-directed come first (shared films first among them), so they sit together in the top row.
L["womendir.grid"] = {"keys": keys, "shape": "circle"}
for v, w in W.items():
    cols, step, r, gap, top = (12, 13, 5.0, 8, 40) if v == "wide" else (10, 13, 5.0, 7, 36)
    cx = w / 2
    pts = {}
    for side, lst, sgn in (("i", IMf, -1), ("l", LBf, 1)):
        order_ = sorted(lst, key=lambda f: (f["wd"] != 1, f["grp"] != "both", f["ir"] if side == "i" else f["lr"]))
        for j, f in enumerate(order_):
            pts[f"{f['id']}:{side}"] = (cx + sgn * (gap + r + (j % cols) * step), top + r + (j // cols) * step)
    h = top + math.ceil(250 / cols) * step + 10
    labs = [{"t": "IMDb", "x": cx - 14, "y": 16, "a": "end", "c": "head imdb"}, {"t": "Letterboxd", "x": cx + 14, "y": 16, "a": "start", "c": "head lb"}]
    L["womendir.grid"][v] = variant(w, h, r, pts, {"labels": labs, "lines": [{"x1": cx, "y1": top - 6, "x2": cx, "y2": h - 6, "c": "spine"}]}, keys)

# ------------------------------------------------------------------ rank ladder (scrollytelling): IMDb's ranks 1-250 in a column left of the
# centre line, Letterboxd's 1-500 in a column to the right (251-500 shaded: outside its Top 250, known only for IMDb's films).
# Keys: every entry on each Top 250 (tt:i, tt:l), plus tt:l for IMDb films Letterboxd ranks 251-500, so their line can be drawn.
# The page draws a line between a film's two dots; y is the rank, so a flat line means the two crowds agree.
lb_out = sorted([f for f in IMf if f.get("lr", 0) > 250], key=lambda f: f["lr"])
rl_keys = [f"{f['id']}:i" for f in IMf] + [f"{f['id']}:l" for f in LBf] + [f"{f['id']}:l" for f in lb_out]
L["ranks.ladder"] = {"keys": rl_keys, "shape": "circle"}
for v, w in W.items():
    step, r, half, top = (1.5, 2.4, 130, 40) if v == "wide" else (1.7, 2.1, 72, 36)
    cx = w / 2
    yr = lambda rank: top + r + (rank - 1) * step
    pts = {f"{f['id']}:i": (cx - half, yr(f["ir"])) for f in IMf}
    pts.update({f"{f['id']}:l": (cx + half, yr(f["lr"])) for f in LBf + lb_out})
    h = yr(500) + r + 12
    ticks = [{"v": str(t), "y": yr(t), "x": cx - half - 12} for t in (1, 50, 100, 150, 200, 250)]
    ticks += [{"v": str(t), "y": yr(t), "x": cx + half + 12} for t in (1, 50, 100, 150, 200, 250, 300, 400, 500)]
    labs = [{"t": "IMDb", "x": cx - 14, "y": 16, "a": "end", "c": "head imdb"}, {"t": "Letterboxd", "x": cx + 14, "y": 16, "a": "start", "c": "head lb"},
            {"t": "Outside its Top 250", "x": cx + half + 12, "y": yr(350), "a": "start", "c": "band-label"}]
    rects = [{"x": cx + half - 8, "y": yr(250.5), "w": 16, "h": yr(500) - yr(250.5) + r, "c": "band"}]
    lines = [{"x1": cx, "y1": top - 6, "x2": cx, "y2": h - 6, "c": "spine"}]
    L["ranks.ladder"][v] = variant(w, h, r, pts, {"labels": labs, "lines": lines, "rects": rects, "yticks": ticks}, rl_keys)

# ------------------------------------------------------------------ hook (scrollytelling, beat 1): two layouts with the same keys, so the
# stage can move every dot from one to the other.
#   hook.split: each list as a block of 250 either side of the centre line, in rank order (filled row by row from the top,
#               starting next to the line).
#   hook.merge: three blocks. Films only on IMDb's list (left), films on both (centre: the film's two dots sit on the same
#               spot, so 111 dots), films only on Letterboxd's (right).
for name in ("hook.split", "hook.merge"):
    L[name] = {"keys": keys, "shape": "circle"}
for v, w in W.items():
    cx = w / 2
    # split
    cols, step, r, gap, top = (12, 13, 5.0, 8, 40) if v == "wide" else (10, 13, 5.0, 7, 36)
    pts = {}
    for side, lst, sgn in (("i", IMf, -1), ("l", LBf, 1)):
        for j, f in enumerate(lst):  # IMf / LBf are already in rank order
            pts[f"{f['id']}:{side}"] = (cx + sgn * (gap + r + (j % cols) * step), top + r + (j // cols) * step)
    h = top + math.ceil(250 / cols) * step + 10
    labs = [{"t": "IMDb", "x": cx - 14, "y": 16, "a": "end", "c": "head imdb"}, {"t": "Letterboxd", "x": cx + 14, "y": 16, "a": "start", "c": "head lb"}]
    L["hook.split"][v] = variant(w, h, r, pts, {"labels": labs, "lines": [{"x1": cx, "y1": top - 6, "x2": cx, "y2": h - 6, "c": "spine"}]}, keys)
    # merge
    cols3, step3, r3, top3 = (10, 13, 5.0, 96) if v == "wide" else (7, 11, 4.2, 92)
    bw = (cols3 - 1) * step3
    g3 = (w - 3 * bw) / 4
    xs = [g3, 2 * g3 + bw, 3 * g3 + 2 * bw]
    groups3 = [[f"{f['id']}:i" for f in IMf if f["grp"] == "imdb"], [f["id"] for f in IMf if f["grp"] == "both"],
               [f"{f['id']}:l" for f in LBf if f["grp"] == "lb"]]
    pts = {}
    for gi, members in enumerate(groups3):
        for j, k in enumerate(members):
            xy_ = (xs[gi] + (j % cols3) * step3, top3 + r3 + (j // cols3) * step3)
            if gi == 1:
                pts[f"{k}:i"] = pts[f"{k}:l"] = xy_
            else:
                pts[k] = xy_
    rows3 = max(math.ceil(len(m) / cols3) for m in groups3)
    h3 = top3 + r3 + (rows3 - 1) * step3 + r3 + 12
    # phones get the shortest names: the counts sit right under them
    names = ([("IMDb only", "imdb", "{overlap.imdb_only}"), ("On both", "both", "{overlap.both}"), ("Letterboxd only", "lb", "{overlap.lb_only}")]
             if v == "wide" else [("IMDb", "imdb", "{overlap.imdb_only}"), ("Both", "both", "{overlap.both}"), ("Letterboxd", "lb", "{overlap.lb_only}")])
    labs = []
    for gi, (t, c, ph) in enumerate(names):
        labs += [{"t": t, "x": xs[gi] + bw / 2, "y": 30, "a": "middle", "c": f"group {c}"},
                 {"t": ph, "x": xs[gi] + bw / 2, "y": 70, "a": "middle", "c": f"big {c}"}]
    L["hook.merge"][v] = variant(w, max(h, h3), r3, pts, {"labels": labs}, keys)

# ------------------------------------------------------------------ mirrored swarms: year and runtime
def mirrored(name, value, lo, hi, ticks, fmt, med, radius=(3.2, 2.2)):
    L[name] = {"keys": keys, "shape": "circle", "domain": [lo, hi]}
    for v, w in W.items():
        m, r = (40, radius[0]) if v == "wide" else (18, radius[1])
        sx = lambda val: m + (val - lo) / (hi - lo) * (w - 2 * m)
        up = dodge([(f"{f['id']}:i", sx(value(f))) for f in IMf], r, "up")
        dn = dodge([(f"{f['id']}:l", sx(value(f))) for f in LBf], r, "down")
        top_ext = -min(up.values()) + r
        axis = 48 + top_ext + 6
        pts = {k: (sx(value(by[k.split(':')[0]])), axis - 8 + off) for k, off in up.items()}
        pts.update({k: (sx(value(by[k.split(':')[0]])), axis + 30 + off) for k, off in dn.items()})
        bottom = axis + 30 + max(dn.values()) + r + 38
        tk = list(ticks)
        bands = [{"x": sx(a), "y": 26, "w": sx(b) - sx(a), "h": bottom - 46, "c": "band"} for a, b in zip(tk[::2], tk[1::2])]
        mi, ml = NUM[f"{med}.imdb"], NUM[f"{med}.lb"]
        deco = {"xticks": [{"v": fmt(t), "x": sx(t), "y": axis + 11} for t in ticks],
                "rects": bands,
                "lines": [{"x1": m, "y1": axis + 7, "x2": w - m, "y2": axis + 7, "c": "axis"},
                          {"x1": sx(mi), "y1": 24, "x2": sx(mi), "y2": axis + 2, "c": "median-imdb"},
                          {"x1": sx(ml), "y1": axis + 24, "x2": sx(ml), "y2": bottom - 18, "c": "median-lb"}],
                "labels": [{"t": "IMDb", "x": m, "y": 18, "a": "start", "c": "head imdb"},
                           {"t": "Letterboxd", "x": m, "y": bottom - 6, "a": "start", "c": "head lb"},
                           {"t": "Median {" + med + ".imdb}", "x": sx(mi) + 5, "y": 34, "a": "start", "c": "median imdb"},
                           {"t": "Median {" + med + ".lb}", "x": sx(ml) + 5, "y": bottom - 20, "a": "start", "c": "median lb"}]}
        L[name][v] = variant(w, bottom, r, pts, deco, keys)


mirrored("year.swarm", lambda f: f["y"], 1918, 2028, range(1920, 2031, 10), lambda t: f"{t}s", "year.median", (4.2, 2.6))
mirrored("runtime.swarm", lambda f: f["rt"], 30, 450, range(60, 451, 60), lambda t: f"{t // 60}h" if t % 60 == 0 else str(t), "runtime.median")

# ------------------------------------------------------------------ waffle: who is billed first
L["waffle.lead"] = {"keys": keys, "shape": "square"}
for v, w in W.items():
    cell, r = (13, 5.2) if v == "wide" else (13, 5.2)
    pts, labs = {}, []
    for bi, (side, lst) in enumerate((("i", IMf), ("l", LBf))):
        ent = sorted(lst, key=lambda f: ({1: 0, 0: 1}.get(f.get("lw"), 2), f["ir"] if side == "i" else f["lr"]))
        if v == "wide":
            x0, y0 = (w / 2 - 25 * cell - 30 if bi == 0 else w / 2 + 30), 96
        else:
            x0, y0 = (w - 25 * cell) / 2 + cell / 2, 96 + bi * (10 * cell + 104)
        if v == "wide":
            x0 += cell / 2
        for j, f in enumerate(ent):
            pts[f"{f['id']}:{side}"] = (x0 + (j % 25) * cell, y0 + (j // 25) * cell)
        nm, tint = ("imdb", "imdb") if side == "i" else ("lb", "lb")
        lx = x0 - cell / 2
        labs += [{"t": "IMDb Top 250" if side == "i" else "Letterboxd Top 250", "x": lx, "y": y0 - 62, "a": "start", "c": f"head {tint}"},
                 {"t": "{gender.lead_woman." + nm + ".n}", "x": lx, "y": y0 - 20, "a": "start", "c": f"big {tint}"},
                 {"t": "of {gender.lead_woman." + nm + ".of} films have a woman billed first", "x": lx + 44, "y": y0 - 34, "a": "start", "c": "sub"},
                 {"t": "({gender.lead_woman." + nm + ".pct}%)", "x": lx + 44, "y": y0 - 20, "a": "start", "c": "sub"}]
    h = (96 + 10 * cell + 10) if v == "wide" else (96 + 20 * cell + 104 + 10)
    L["waffle.lead"][v] = variant(w, h, r, pts, {"labels": labs}, keys)

# ------------------------------------------------------------------ director filmography strips (4 or more films on either list)
dirs = {}
for side, lst in (("i", IMf), ("l", LBf)):
    for f in lst:
        for d in f["d"]:
            dirs.setdefault(d, {"i": set(), "l": set()})[side].add(f["id"])
strip_dirs = [d for d, s in dirs.items() if max(len(s["i"]), len(s["l"])) >= 4]
lean = lambda d: (len(dirs[d]["i"]) - len(dirs[d]["l"])) / (len(dirs[d]["i"]) + len(dirs[d]["l"]))
strip_dirs.sort(key=lambda d: (-lean(d), -(len(dirs[d]["i"]) + len(dirs[d]["l"])), d))
skeys = []
for d in strip_dirs:
    for i in sorted(dirs[d]["i"] | dirs[d]["l"], key=lambda i: by[i]["y"]):
        skeys.append(f"s:{d}|{i}")
L["directors.strips"] = {"keys": skeys, "shape": "circle", "domain": [1918, 2028], "rows": strip_dirs}
for v, w in W.items():
    if v == "wide":
        lab, m, r, rowh, top = 190, 30, 4.4, 40, 40
    else:
        lab, m, r, rowh, top = 0, 16, 3.4, 52, 40
    sx = lambda y: lab + m + (y - 1918) / 110 * (w - lab - 2 * m)
    pts, labs, lines, y0 = {}, [], [], top
    for d in strip_dirs:
        base = y0 + (rowh - 2 * r) / 2 + (8 if v == "narrow" else 0)
        lanes = {"i": [], "l": [], "b": []}
        for i in dirs[d]["i"] | dirs[d]["l"]:
            lane = "b" if i in dirs[d]["i"] and i in dirs[d]["l"] else "i" if i in dirs[d]["i"] else "l"
            lanes[lane].append((f"s:{d}|{i}", sx(by[i]["y"])))
        # shared films sit on the line; IMDb-only films above it and Letterboxd-only below, all avoiding each other
        placed = []
        offs = dict(dodge(lanes["b"], r, "both", 0.4, placed=placed))
        offs.update(dodge(lanes["i"], r, "up", 0.4, start=r + 1.5, placed=placed))
        offs.update(dodge(lanes["l"], r, "down", 0.4, start=r + 1.5, placed=placed))
        for k, x in lanes["i"] + lanes["l"] + lanes["b"]:
            pts[k] = (x, base + offs[k])
        if v == "wide":
            labs.append({"t": d, "x": lab, "y": base + 4, "a": "end", "c": "row"})
        else:
            labs.append({"t": d, "x": m, "y": y0 + 6, "a": "start", "c": "row"})
        lines.append({"x1": sx(1918), "y1": base, "x2": sx(2028), "y2": base, "c": "grid"})
        y0 += rowh
    deco = {"labels": labs, "lines": lines, "xticks": [{"v": f"{t}", "x": sx(t), "y": y0 + 10} for t in range(1920, 2030, 20)]}
    L["directors.strips"][v] = variant(w, y0 + 24, r, pts, deco, skeys)

# ------------------------------------------------------------------ directors sorted into three groups, sized by film count
groups = {"i": [], "b": [], "l": []}
for d, s in dirs.items():
    g = "b" if s["i"] and s["l"] else "i" if s["i"] else "l"
    groups[g].append((d, len(s["i"] | s["l"])))
dkeys = [f"d:{d}" for g in "ibl" for d, n in sorted(groups[g], key=lambda t: (-t[1], t[0]))]
L["directors.sort"] = {"keys": dkeys, "shape": "circle", "sized": True}


def pack(items, base_r, pad=1.0):
    """Greedy circle packing on a spiral around (0,0). items sorted largest first. Returns {name: (x, y, r)}."""
    out, placed = {}, []
    for name, n in items:
        r = base_r * math.sqrt(n)
        t = 0.0
        while True:
            rad = 0.0 if t == 0 else 1.2 * math.sqrt(t) * base_r
            x, y = rad * math.cos(t * 0.9), rad * math.sin(t * 0.9)
            if all(math.hypot(x - px, y - py) >= r + pr + pad for px, py, pr in placed):
                break
            t += 0.25
        placed.append((x, y, r))
        out[name] = (x, y, r)
    return out


for v, w in W.items():
    base = 3.4 if v == "wide" else 2.6
    packs = {g: pack(sorted(groups[g], key=lambda t: (-t[1], t[0])), base) for g in "ibl"}
    ext = {g: (min(x - r for x, y, r in p.values()), max(x + r for x, y, r in p.values()),
               min(y - r for x, y, r in p.values()), max(y + r for x, y, r in p.values())) for g, p in packs.items()}
    pts, labs, radii = {}, [], {}
    if v == "wide":
        centers = {"i": (w / 6, 0), "b": (w / 2, 0), "l": (5 * w / 6, 0)}
        top = 86 - min(e[2] for e in ext.values())
        centers = {g: (cx, top) for g, (cx, _) in centers.items()}
        h = top + max(e[3] for e in ext.values()) + 12
    else:
        centers, y = {}, 70
        for g in "ibl":
            y += -ext[g][2]
            centers[g] = (w / 2, y)
            y += ext[g][3] + 84
        h = y - 64
    names = {"i": ("Only IMDb", "imdb", "{directors.imdb_only}"), "b": ("On both", "both", "{directors.both}"), "l": ("Only Letterboxd", "lb", "{directors.lb_only}")}
    for g, p in packs.items():
        cx, cy = centers[g]
        for d, (x, y, r) in p.items():
            pts[f"d:{d}"] = (cx + x, cy + y)
            radii[f"d:{d}"] = round(r, 2)
        t, c, n = names[g]
        ly = 42 if v == "wide" else cy + ext[g][2] - 44  # wide: one baseline for all three headings
        labs += [{"t": t, "x": cx, "y": ly, "a": "middle", "c": f"head {c}"}, {"t": n, "x": cx, "y": ly + 28, "a": "middle", "c": f"mid {c}"}]
    var = variant(w, h, base, pts, {"labels": labs}, dkeys)
    var["radii"] = [radii[k] for k in dkeys]
    L["directors.sort"][v] = var

# ------------------------------------------------------------------ rank quadrants (IMDb films that are in Letterboxd's top 500)
pool = [f for f in IMf if "lr" in f]
qkeys = [f"{f['id']}" for f in pool]
L["quadrant.rank"] = {"keys": qkeys, "shape": "circle", "x": [1, 250], "y": [1, 500]}
for v, w in W.items():
    ml, mr, mt, h = (56, 24, 30, 560) if v == "wide" else (40, 14, 30, 420)
    r = 4.2 if v == "wide" else 3.0
    sx = lambda x: ml + (x - 1) / 249 * (w - ml - mr)
    sy = lambda y: mt + (y - 1) / 499 * (h - mt - 40)
    pts = {f["id"]: (sx(f["ir"]), sy(f["lr"])) for f in pool}
    deco = {"lines": [{"x1": sx(125.5), "y1": sy(1), "x2": sx(125.5), "y2": sy(500), "c": "ref"}, {"x1": sx(1), "y1": sy(250.5), "x2": sx(250), "y2": sy(250.5), "c": "ref"}],
            "xticks": [{"v": str(t), "x": sx(t), "y": h - 22} for t in (1, 50, 100, 150, 200, 250)],
            "yticks": [{"v": str(t), "y": sy(t), "x": ml - 8} for t in (1, 100, 200, 300, 400, 500)],
            "labels": [{"t": "IMDb rank", "x": w - mr, "y": h - 4, "a": "end", "c": "axis-title"},
                       {"t": "Letterboxd rank", "x": ml, "y": 14, "a": "start", "c": "axis-title"},
                       {"t": "High on both · {quadrant.rank.both}", "x": sx(4), "y": sy(242), "a": "start", "c": "quad"},
                       {"t": "Higher on Letterboxd · {quadrant.rank.lb}", "x": sx(247), "y": sy(242), "a": "end", "c": "quad"},
                       {"t": "Higher on IMDb · {quadrant.rank.imdb}", "x": sx(4), "y": sy(492), "a": "start", "c": "quad"},
                       {"t": "Lower on both · {quadrant.rank.neither}", "x": sx(247), "y": sy(492), "a": "end", "c": "quad"}]}
    L["quadrant.rank"][v] = variant(w, h, r, pts, deco, qkeys)

# ------------------------------------------------------------------ rating quadrants (all 389 films)
nums = json.load(open(SITE / "numbers.json", encoding="utf-8"))["n"]
mi, ml_ = nums["rating.imdb_median_all"], nums["rating.lb_median_all"]
ckeys = [f["id"] for f in sorted(films, key=lambda f: f["id"])]
xr = [math.floor(min(f["iR"] for f in films) * 10 - 1) / 10, math.ceil(max(f["iR"] for f in films) * 10 + 1) / 10]
yr = [math.floor(min(f["lR"] for f in films) * 10 - 1) / 10, math.ceil(max(f["lR"] for f in films) * 10 + 1) / 10]
jit = lambda i: (int(hashlib.md5(i.encode()).hexdigest()[:6], 16) / 0xFFFFFF - 0.5) * 0.07  # stays inside the film's 0.1 IMDb step
L["quadrant.rating"] = {"keys": ckeys, "shape": "circle", "x": xr, "y": yr, "jitter": 0.035}
for v, w in W.items():
    ml, mr, mt, h = (56, 24, 30, 560) if v == "wide" else (40, 14, 30, 440)
    r = 3.6 if v == "wide" else 2.6
    sx = lambda x: ml + (x - xr[0]) / (xr[1] - xr[0]) * (w - ml - mr)
    sy = lambda y: mt + (yr[1] - y) / (yr[1] - yr[0]) * (h - mt - 40)
    pts = {f["id"]: (sx(f["iR"] + jit(f["id"])), sy(f["lR"])) for f in films}
    xt = [round(xr[0] + 0.2 * k, 1) for k in range(0, 30) if xr[0] + 0.2 * k <= xr[1] + 1e-9]
    yt = [round(math.ceil(yr[0] * 5) / 5 + 0.2 * k, 1) for k in range(0, 30) if math.ceil(yr[0] * 5) / 5 + 0.2 * k <= yr[1] + 1e-9]
    deco = {"lines": [{"x1": sx(mi), "y1": sy(yr[0]), "x2": sx(mi), "y2": sy(yr[1]), "c": "ref"}, {"x1": sx(xr[0]), "y1": sy(ml_), "x2": sx(xr[1]), "y2": sy(ml_), "c": "ref"}],
            "xticks": [{"v": f"{t:.1f}", "x": sx(t), "y": h - 22} for t in xt],
            "yticks": [{"v": f"{t:.1f}", "y": sy(t), "x": ml - 8} for t in yt],
            "labels": [{"t": "IMDb rating", "x": w - mr, "y": h - 4, "a": "end", "c": "axis-title"},
                       {"t": "Letterboxd rating (out of 10)", "x": ml, "y": 14, "a": "start", "c": "axis-title"},
                       {"t": "High on both · {quadrant.rating.both_high}", "x": w - mr - 4, "y": mt + 12, "a": "end", "c": "quad"},
                       {"t": "Letterboxd rates higher · {quadrant.rating.lb_higher}", "x": ml + 6, "y": mt + 12, "a": "start", "c": "quad"},
                       {"t": "IMDb rates higher · {quadrant.rating.imdb_higher}", "x": w - mr - 4, "y": h - 52, "a": "end", "c": "quad"},
                       {"t": "Lower on both · {quadrant.rating.both_low}", "x": ml + 6, "y": h - 52, "a": "start", "c": "quad"}]}
    L["quadrant.rating"][v] = variant(w, h, r, pts, deco, ckeys)

json.dump({"variants": W, "layouts": L}, open(SITE / "layouts.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"layouts.json: {len(L)} layouts -> data/site/layouts.json ({(SITE / 'layouts.json').stat().st_size // 1024} KB)")
for name, lay in L.items():
    print(f"  {name:18s} {len(lay['keys']):4d} dots   wide {lay['wide']['w']}x{lay['wide']['h']}   narrow {lay['narrow']['w']}x{lay['narrow']['h']}")

#!/usr/bin/env python3
"""
Fix HoI4 MAP_ERRORs:
  no air base site / rocket site / gun emplacement defined for state N

Appends missing entries to map/buildings.txt, placed on a land province
of each state (largest one, near its centre, safely away from borders).

Usage:
    pip install pillow numpy
    python fix_buildings.py "C:/path/to/your/mod"
"""
import re
import sys
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Building names as they appear in map/buildings.txt.
# Offsets (in pixels) keep the buildings from stacking on each other.
BUILDINGS = {
    "air_base": (0, 0),
    "rocket_site_spawn": (3, 0),
}
LAND_Y = 9.50  # standard land height used by vanilla buildings.txt


def read(path):
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def load_definitions(mod):
    """province id -> (rgb key, type)"""
    defs = {}
    for line in read(mod / "map" / "definition.csv").splitlines():
        p = line.strip().split(";")
        if len(p) < 5 or not p[0].isdigit():
            continue
        pid = int(p[0])
        r, g, b = int(p[1]), int(p[2]), int(p[3])
        defs[pid] = ((r << 16) | (g << 8) | b, p[4].strip().lower())
    return defs


def load_states(mod):
    """state id -> list of province ids"""
    states = {}
    for f in sorted((mod / "history" / "states").glob("*.txt")):
        txt = read(f)
        m_id = re.search(r"\bid\s*=\s*(\d+)", txt)
        m_pr = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", txt)
        if not m_id or not m_pr:
            print(f"  [warn] could not parse {f.name}, skipping")
            continue
        states[int(m_id.group(1))] = [int(x) for x in m_pr.group(1).split()]
    return states


def load_existing(path):
    have = set()
    for line in read(path).splitlines():
        p = line.strip().split(";")
        if len(p) >= 2 and p[0].isdigit():
            have.add((int(p[0]), p[1]))
    return have


def check_building_names(mod):
    """Warn if a building name isn't defined in common/buildings."""
    d = mod / "common" / "buildings"
    if not d.exists():
        return
    text = "\n".join(read(f) for f in d.glob("*.txt"))
    for name in BUILDINGS:
        if not re.search(rf"\b{name}\s*=\s*\{{", text):
            print(f"  [warn] '{name}' not found in common/buildings/*.txt "
                  f"- check the name used by your version/mod")


def interior(xs, ys, margin=2):
    """Keep only pixels at least `margin` px away from the province edge."""
    if len(xs) == 0:
        return xs, ys
    x0, y0 = xs.min(), ys.min()
    mask = np.zeros((ys.max() - y0 + 1, xs.max() - x0 + 1), bool)
    mask[ys - y0, xs - x0] = True
    for m in (margin, 1, 0):
        e = mask.copy()
        for _ in range(m):
            p = np.pad(e, 1)
            e = e & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        r, c = np.nonzero(e)
        if len(r):
            return c + x0, r + y0
    return xs, ys


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    mod = Path(sys.argv[1])
    bfile = mod / "map" / "buildings.txt"
    if not bfile.exists():
        sys.exit(f"Not found: {bfile}")

    print("Reading definitions and states...")
    defs = load_definitions(mod)
    states = load_states(mod)
    existing = load_existing(bfile)
    check_building_names(mod)

    # Which (state, building) pairs are missing?
    missing = {
        sid: [b for b in BUILDINGS if (sid, b) not in existing]
        for sid in states
    }
    missing = {s: b for s, b in missing.items() if b}
    if not missing:
        print("Nothing to add - all states already have these buildings.")
        return
    print(f"{len(missing)} states need entries.")

    print("Loading provinces.bmp (this can take a few seconds)...")
    img = np.asarray(Image.open(mod / "map" / "provinces.bmp").convert("RGB"))
    h, w, _ = img.shape
    keys = (img[:, :, 0].astype(np.int32) << 16) | \
           (img[:, :, 1].astype(np.int32) << 8) | img[:, :, 2].astype(np.int32)
    flat = keys.ravel()
    order = np.argsort(flat, kind="stable")
    sorted_keys = flat[order]
    uniq, starts, counts = np.unique(sorted_keys, return_index=True,
                                     return_counts=True)
    key_to_slice = {int(k): (int(s), int(c))
                    for k, s, c in zip(uniq, starts, counts)}

    def province_pixels(pid):
        key = defs[pid][0]
        if key not in key_to_slice:
            return None
        s, c = key_to_slice[key]
        idx = order[s:s + c]
        return idx % w, idx // w  # xs, ys

    lines = []
    skipped = []
    for sid in sorted(missing):
        # pick the largest land province in the state
        best, best_n = None, 0
        for pid in states[sid]:
            if pid not in defs or defs[pid][1] != "land":
                continue
            px = province_pixels(pid)
            if px is not None and len(px[0]) > best_n:
                best, best_n = px, len(px[0])
        if best is None:
            skipped.append(sid)
            continue
        
        xs, ys = best
        xs, ys = interior(xs, ys, 2)  # Avoid placing on borders
        cx, cy = xs.mean(), ys.mean()
        
        for name in missing[sid]:
            dx, dy = BUILDINGS[name]
            tx, ty = cx + dx, cy + dy
            i = np.argmin((xs - tx) ** 2 + (ys - ty) ** 2)
            x, y = int(xs[i]), int(ys[i])
            z = h - y  # buildings.txt Z axis is flipped vs. the bitmap
            lines.append(f"{sid};{name};{x:.2f};{LAND_Y:.2f};{z:.2f};0.00;0")

    if skipped:
        print(f"[warn] no land province found for states: {skipped}")

    backup = bfile.with_suffix(".txt.bak")
    if not backup.exists():
        shutil.copy2(bfile, backup)
        print(f"Backup written: {backup}")

    raw = bfile.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.endswith(("\n", "\r")):
        text += nl
    text += nl.join(lines) + nl
    bfile.write_text(text, encoding="utf-8", newline="")
    print(f"Added {len(lines)} lines to {bfile}")


if __name__ == "__main__":
    main()
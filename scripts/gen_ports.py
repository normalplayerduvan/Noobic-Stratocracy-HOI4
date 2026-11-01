import os, re, glob
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
MOD = os.path.expanduser("~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/NSTNO")

# --- definition.csv
defs, color2id = {}, {}
with open(f"{MOD}/map/definition.csv", encoding="utf-8-sig") as f:
    for line in f:
        p = line.strip().split(";")
        if len(p) < 6 or not p[0].isdigit():
            continue
        pid = int(p[0])
        color2id[(int(p[1]), int(p[2]), int(p[3]))] = pid
        defs[pid] = (p[4].lower(), p[5].lower() == "true")

N = max(defs) + 1
land = np.zeros(N, bool); sea = np.zeros(N, bool); coast = np.zeros(N, bool)
for pid, (t, c) in defs.items():
    if t == "land":
        land[pid] = True
        coast[pid] = c
    elif t == "sea":
        sea[pid] = True

# --- province id map
img = np.array(Image.open(f"{MOD}/map/provinces.bmp").convert("RGB"))
H, W = img.shape[:2]
key = (img[..., 0].astype(np.int64) << 16) | (img[..., 1].astype(np.int64) << 8) | img[..., 2]
uniq, inv = np.unique(key.ravel(), return_inverse=True)
lut = np.array([color2id.get(((k >> 16) & 255, (k >> 8) & 255, k & 255), 0) for k in uniq])
ids = lut[inv].reshape(H, W)

# --- coastal land pixels that touch a sea pixel
P, X, Y, S = [], [], [], []
for shift in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    nb = np.roll(ids, shift, axis=(0, 1))
    m = land[ids] & coast[ids] & sea[nb]
    ys, xs = np.nonzero(m)
    P.append(ids[ys, xs]); X.append(xs); Y.append(ys); S.append(nb[ys, xs])
P = np.concatenate(P); X = np.concatenate(X); Y = np.concatenate(Y); S = np.concatenate(S)

# --- province -> state
prov2state = {}
for fn in glob.glob(f"{MOD}/history/states/*.txt"):
    txt = open(fn, encoding="utf-8-sig").read()
    m = re.search(r"\bid\s*=\s*(\d+)", txt)
    b = re.search(r"provinces\s*=\s*\{([^}]*)\}", txt)
    if m and b:
        for pv in b.group(1).split():
            prov2state[int(pv)] = int(m.group(1))

# --- one naval_base per coastal province, at the candidate nearest the centroid
rows, no_sea, no_state = [], [], []
for pid in np.nonzero(coast)[0]:
    sel = P == pid
    if not sel.any():
        no_sea.append(int(pid)); continue
    if pid not in prov2state:
        no_state.append(int(pid)); continue
    xs, ys, ss = X[sel], Y[sel], S[sel]
    i = np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2)
    rows.append((prov2state[pid], f"{xs[i] + 0.5:.2f}", f"{H - ys[i] - 0.5:.2f}", int(ss[i])))

rows.sort()
out = f"{MOD}/map/buildings.txt"
if os.path.exists(out):
    os.replace(out, out + ".bak")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    for st, x, z, sp in rows:
        f.write(f"{st};naval_base;{x};9.50;{z};0.00;{sp}\n")

print("written:", len(rows))
print("coastal but touches no sea pixel (fix flag in definition.csv):", no_sea)
print("coastal but in no state:", no_state)
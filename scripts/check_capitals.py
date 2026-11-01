import os, re, glob

MOD = os.path.expanduser("~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/NSTNO")

def read(p):
    return open(p, "rb").read().decode("utf-8-sig", errors="replace")

states = {}   # id -> (file, owner, has_vp, provinces)
for fn in glob.glob(f"{MOD}/history/states/*.txt"):
    t = read(fn)
    m = re.search(r"^\s*id\s*=\s*(\d+)", t, re.M)
    if not m:
        continue
    o = re.search(r"\bowner\s*=\s*(\w+)", t)
    b = re.search(r"provinces\s*=\s*\{([^}]*)\}", t)
    states[int(m.group(1))] = (
        os.path.basename(fn),
        o.group(1) if o else None,
        bool(re.search(r"victory_points\s*=\s*\{\s*\d+\s+\d+", t)),
        len(b.group(1).split()) if b else 0,
    )

owned = {}
for sid, (_, own, _, _) in states.items():
    if own:
        owned.setdefault(own, []).append(sid)

for fn in sorted(glob.glob(f"{MOD}/history/countries/*.txt")):
    base = os.path.basename(fn)
    tag = base.split(" ")[0].split("-")[0].strip()
    t = read(fn)
    m = re.search(r"^\s*capital\s*=\s*(\d+)", t, re.M)
    if not m:
        if tag in owned:
            print(f"{base}: NO capital line, but owns {len(owned[tag])} states")
        continue
    cap = int(m.group(1))
    if cap not in states:
        print(f"{base}: capital {cap} DOES NOT EXIST")
        continue
    f, own, vp, nprov = states[cap]
    probs = []
    if own != tag:
        probs.append(f"owned by {own}, not {tag}")
    if not vp:
        probs.append("no victory point")
    if nprov == 0:
        probs.append("no provinces")
    if probs:
        print(f"{base}: capital {cap} ({f}): " + ", ".join(probs))
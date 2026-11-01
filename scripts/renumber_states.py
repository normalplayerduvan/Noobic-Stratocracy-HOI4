import os, re, sys, glob, shutil, time
from collections import defaultdict

MOD = os.path.expanduser("~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/NSTNO")
APPLY = "--apply" in sys.argv
STATES = os.path.normpath(f"{MOD}/history/states")

def read(p):
    b = open(p, "rb").read()
    return b.decode("utf-8-sig"), b.startswith(b"\xef\xbb\xbf")

def write(p, s, bom):
    with open(p, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))

ID_RE = re.compile(r"^(\s*id\s*=\s*)(\d+)", re.M)
PROV_RE = re.compile(r"provinces\s*=\s*\{([^}]*)\}")
KEYED = re.compile(r"(\b(?:\w*state|capital|set_capital)\s*=\s*)(\d+)\b")
BARE = re.compile(r"^\s*(\d+)\s*=\s*\{", re.M)

# ---------- 1. read all state files
entries, prov_owner = [], defaultdict(list)
for fn in glob.glob(f"{STATES}/*.txt"):
    txt, _ = read(fn)
    m = ID_RE.search(txt)
    name = os.path.basename(fn)
    if not m:
        print("WARNING: no id, skipped:", name)
        continue
    entries.append((int(m.group(2)), name))
    b = PROV_RE.search(txt)
    if b:
        for pv in b.group(1).split():
            prov_owner[pv].append(name)
entries.sort(key=lambda e: (e[0], e[1]))

# ---------- 2. plan: new id = position in sorted order
plan, mapping, ambiguous = [], {}, set()
for new, (old, name) in enumerate(entries, 1):
    plan.append((old, name, new))
    if old in mapping:
        ambiguous.add(old)
    else:
        mapping[old] = new
changed = [p for p in plan if p[0] != p[2]]

print(f"{len(plan)} state files, {len(changed)} will change ID")
if ambiguous:
    print("DUPLICATE IDs (later file in sort order gets a fresh ID):")
    for old in sorted(ambiguous):
        print("  ", old, [n for o, n, _ in plan if o == old])
shared = {p: f for p, f in prov_owner.items() if len(f) > 1}
if shared:
    print(f"PROVINCES CLAIMED BY MORE THAN ONE STATE: {len(shared)} (fix these by hand)")
    for p, f in list(shared.items())[:20]:
        print("  province", p, f)
for old, name, new in changed[:15]:
    print(f"  {old} -> {new}  {name}")
if len(changed) > 15:
    print(f"  ... and {len(changed) - 15} more")

# ---------- 3. references in other files
missing, bare_hits = [], []

def ref_files():
    for sub in ("common", "events", "history"):
        for root, _, fs in os.walk(f"{MOD}/{sub}"):
            if os.path.normpath(root).startswith(STATES):
                continue
            for f in fs:
                if f.endswith(".txt"):
                    yield os.path.join(root, f)

edits = []  # (path, new_text, bom)
for p in ref_files():
    try:
        txt, bom = read(p)
    except Exception:
        continue
    def sub(m, p=p):
        v = int(m.group(2))
        if v in mapping:
            return m.group(1) + str(mapping[v])
        missing.append((os.path.relpath(p, MOD), v))
        return m.group(0)
    new = KEYED.sub(sub, txt)
    if new != txt:
        edits.append((p, new, bom))
    if not p.startswith(f"{MOD}/history/"):
        for m in BARE.finditer(txt):
            bare_hits.append((os.path.relpath(p, MOD), txt[:m.start()].count("\n") + 2, m.group(1)))

print(f"\nreferences auto-rewritten in {len(edits)} files (state=N, owns_state=N, capital=N, ...)")
if missing:
    print(f"REFERENCES TO IDs THAT NO LONGER EXIST ({len(missing)}), left untouched, repoint these by hand:")
    for rel, v in missing[:40]:
        print("  ", rel, v)
if bare_hits:
    print(f"\nBARE 'N = {{' BLOCKS (could be state scopes, NOT auto-changed): {len(bare_hits)}")
    for rel, ln, v in bare_hits[:25]:
        print(f"   {rel}:{ln}: {v} = {{")

if not APPLY:
    sys.exit("\nDry run only. Re-run with --apply to make the changes.")

# ---------- 4. backup
bk = os.path.expanduser(f"~/nstno_states_backup_{int(time.time())}")
os.makedirs(bk)
for rel in ("history", "common", "events", "map/supplyareas", "localisation"):
    if os.path.isdir(f"{MOD}/{rel}"):
        shutil.copytree(f"{MOD}/{rel}", f"{bk}/{rel}")
shutil.copy(f"{MOD}/map/buildings.txt", f"{bk}/buildings.txt")
with open(f"{bk}/state_id_map.txt", "w") as f:
    for old, name, new in plan:
        f.write(f"{old};{new};{name}\n")
print("backup in", bk)

# ---------- 5. state files: rewrite contents, then two-phase rename
tmp = []
for old, name, new in plan:
    if old == new:
        continue
    fn = f"{STATES}/{name}"
    txt, bom = read(fn)
    txt = ID_RE.sub(lambda m: m.group(1) + str(new), txt, count=1)
    txt = re.sub(r"STATE_(\d+)(?!\d)", lambda m: f"STATE_{new}" if int(m.group(1)) == old else m.group(0), txt)
    write(fn, txt, bom)
    m = re.match(r"^(\d+)-(.*)$", name)
    if m and int(m.group(1)) == old:
        t = f"{STATES}/__tmp_{new}__.txt"
        os.rename(fn, t)
        tmp.append((t, f"{STATES}/{new}-{m.group(2)}"))
for t, final in tmp:
    os.rename(t, final)

# ---------- 6. other references
for p, new, bom in edits:
    write(p, new, bom)

def remap(m):
    return str(mapping.get(int(m.group()), int(m.group())))

for fn in glob.glob(f"{MOD}/map/supplyareas/*.txt"):
    txt, bom = read(fn)
    new = re.sub(r"(states\s*=\s*\{)([^}]*)(\})",
                 lambda m: m.group(1) + re.sub(r"\d+", remap, m.group(2)) + m.group(3), txt)
    if new != txt:
        write(fn, new, bom)

for fn in glob.glob(f"{MOD}/localisation/**/*.yml", recursive=True):
    txt, bom = read(fn)
    new = re.sub(r"STATE_(\d+)(?!\d)", lambda m: f"STATE_{mapping.get(int(m.group(1)), int(m.group(1)))}", txt)
    if new != txt:
        write(fn, new, bom)

p = f"{MOD}/map/buildings.txt"
txt, bom = read(p)
rows, dropped = [], 0
for line in txt.replace("\r", "").split("\n"):
    if not line.strip():
        continue
    f = line.split(";")
    if int(f[0]) not in mapping:
        dropped += 1
        continue
    f[0] = str(mapping[int(f[0])])
    rows.append(f)
rows.sort(key=lambda f: int(f[0]))
write(p, "\n".join(";".join(f) for f in rows), bom)
print(f"buildings.txt: {len(rows)} lines kept, {dropped} dropped (state no longer exists)")
print("done")
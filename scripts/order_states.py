import os, re, sys, glob, shutil, time
from collections import Counter

MOD = os.path.expanduser("~/.local/share/Paradox Interactive/Hearts of Iron IV/mod/NSTNO")
STATES = f"{MOD}/history/states"
APPLY = "--apply" in sys.argv
NAMES = "--names" in sys.argv

def read(p):
    b = open(p, "rb").read()
    return b.decode("utf-8-sig"), b.startswith(b"\xef\xbb\xbf")

def write(p, s, bom):
    with open(p, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))

ID_RE = re.compile(r"^(\s*id\s*=\s*)(\d+)", re.M)
NAME_RE = re.compile(r'(\bname\s*=\s*"STATE_)(\d+)(")')
PREFIX_RE = re.compile(r"^(\d+)-(.*)$")

# ---- read every state file
info = []   # (path, id, name_num or None)
for fn in sorted(glob.glob(f"{STATES}/*.txt")):
    txt, _ = read(fn)
    m = ID_RE.search(txt)
    if not m:
        print("WARNING: no id, skipped:", os.path.basename(fn)); continue
    n = NAME_RE.search(txt)
    info.append((fn, int(m.group(2)), int(n.group(2)) if n else None))

ids = [i for _, i, _ in info]
cnt = Counter(ids)
dups = sorted(i for i, c in cnt.items() if c > 1)
gaps = [i for i in range(1, len(info) + 1) if i not in cnt]
if dups or gaps or max(ids) != len(info):
    print("IDs are not exactly 1..N, run renumber_states.py first.")
    print("duplicates:", dups, "gaps:", gaps, "highest:", max(ids), "files:", len(info))
    sys.exit(1)
print(f"{len(info)} state files, IDs are a clean 1..{len(info)}")

# ---- filename plan
renames, no_prefix = [], 0
for fn, sid, _ in info:
    base = os.path.basename(fn)
    m = PREFIX_RE.match(base)
    if not m:
        no_prefix += 1; continue
    if int(m.group(1)) != sid:
        renames.append((fn, os.path.join(STATES, f"{sid}-{m.group(2)}")))
print(f"filenames to fix: {len(renames)} ({no_prefix} files have no numeric prefix and are left alone)")
for a, b in renames[:12]:
    print("  ", os.path.basename(a), "->", os.path.basename(b))
if len(renames) > 12:
    print(f"   ... and {len(renames) - 12} more")

# ---- name key plan
mapping, name_edits = {}, []
if NAMES:
    srcs = Counter(k for _, _, k in info if k is not None)
    shared = sorted(k for k, c in srcs.items() if c > 1)
    if shared:
        print("STATE_ names used by more than one state file, fix by hand:", shared)
        sys.exit(1)
    for fn, sid, k in info:
        if k is not None and k != sid:
            mapping[k] = sid
            name_edits.append((fn, sid))
    print(f"name keys to sync: {len(mapping)}")
    for k, v in list(mapping.items())[:8]:
        print(f"   STATE_{k} -> STATE_{v}")
    yml_nums = set()
    for fn in glob.glob(f"{MOD}/localisation/**/*.yml", recursive=True):
        yml_nums |= {int(x) for x in re.findall(r"STATE_(\d+)(?!\d)", read(fn)[0])}
    clash = sorted(t for t in set(mapping.values()) if t in yml_nums and t not in mapping)
    if clash:
        print("localisation already has unused STATE_ keys at these new numbers (duplicate keys after the sync):", clash[:30])

if not APPLY:
    sys.exit("\nDry run only. Re-run with --apply to make the changes.")

# ---- backup
bk = os.path.expanduser(f"~/nstno_states_order_backup_{int(time.time())}")
os.makedirs(bk)
shutil.copytree(STATES, f"{bk}/history_states")
if os.path.isdir(f"{MOD}/localisation"):
    shutil.copytree(f"{MOD}/localisation", f"{bk}/localisation")
print("backup in", bk)

# ---- name edits (inside state files)
for fn, sid in name_edits:
    txt, bom = read(fn)
    write(fn, NAME_RE.sub(lambda m: f"{m.group(1)}{sid}{m.group(3)}", txt, count=1), bom)

# ---- renames, two phase so nothing collides
tmp = []
for i, (a, b) in enumerate(renames):
    t = os.path.join(STATES, f"__tmp_{i}__.txt")
    os.rename(a, t); tmp.append((t, b))
for t, b in tmp:
    os.rename(t, b)

# ---- localisation, one simultaneous pass so chains can't collide
if NAMES and mapping:
    for fn in glob.glob(f"{MOD}/localisation/**/*.yml", recursive=True):
        txt, bom = read(fn)
        new = re.sub(r"STATE_(\d+)(?!\d)", lambda m: f"STATE_{mapping.get(int(m.group(1)), int(m.group(1)))}", txt)
        if new != txt:
            write(fn, new, bom)
print("done")

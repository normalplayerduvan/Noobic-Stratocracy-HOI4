import re
import shutil
from pathlib import Path

REGION_FILE = Path("../map/strategicregions/1-Test Strategic Region.txt")
IDS_FILE = Path("ids.txt")
# Load IDs to remove
remove = set(int(x) for x in re.findall(r"\d+", IDS_FILE.read_text()))

text = REGION_FILE.read_text(encoding="utf-8")

# Match the provinces block
pattern = re.compile(r"(provinces\s*=\s*\{)([^}]*)(\})", re.DOTALL)
m = pattern.search(text)
if not m:
    raise SystemExit("No provinces = { ... } block found.")

current = [int(x) for x in re.findall(r"\d+", m.group(2))]
kept = [p for p in current if p not in remove]
removed = [p for p in current if p in remove]
not_found = sorted(remove - set(current))

# Rebuild block, 20 IDs per line, tab-indented
lines = ["\t\t" + " ".join(map(str, kept[i:i + 20])) for i in range(0, len(kept), 20)]
new_block = m.group(1) + "\n" + "\n".join(lines) + "\n\t" + m.group(3)

# Backup, then write
shutil.copy(REGION_FILE, REGION_FILE.with_suffix(".txt.bak"))
REGION_FILE.write_text(text[:m.start()] + new_block + text[m.end():], encoding="utf-8")

print(f"Removed {len(removed)} provinces, {len(kept)} remain.")
print(f"{len(not_found)} IDs from your list weren't in this region.")
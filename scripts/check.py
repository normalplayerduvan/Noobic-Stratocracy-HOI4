import re
from pathlib import Path

ids = set(map(int, re.findall(r"\d+", Path("ids.txt").read_text())))
region = Path("../map/strategicregions/1-Test Strategic Region.txt")
t = region.read_text(encoding="utf-8")
cur = set(map(int, re.findall(r"\d+", re.search(r"provinces\s*=\s*\{([^}]*)\}", t, re.S).group(1))))

print("listed IDs still in file:", len(ids & cur))
print("provinces in file:", len(cur))
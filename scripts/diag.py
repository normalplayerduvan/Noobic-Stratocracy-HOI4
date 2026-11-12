from pathlib import Path
import numpy as np
from PIL import Image
import buildings as b

Image.MAX_IMAGE_PIXELS = None
mod = Path("..")
defs = b.load_definitions(mod)
states = b.load_states(mod)
img = np.asarray(Image.open(mod / "map" / "provinces.bmp").convert("RGB")).astype(np.int32)
keys = (img[:, :, 0] << 16) | (img[:, :, 1] << 8) | img[:, :, 2]

for sid in [34, 69, 101, 161, 176, 224, 323, 326, 428]:
    print(f"state {sid}:")
    for pid in states.get(sid, []):
        if pid not in defs:
            print(f"  province {pid}: NOT in definition.csv")
            continue
        key, ptype = defs[pid]
        print(f"  province {pid}: type={ptype} pixels={(keys == key).sum()}")
"""Generate a small known-shift demo; contains no experimental images."""

import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np, tifffile
from scipy.ndimage import gaussian_filter, shift

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=False)
rng = np.random.default_rng(82)
ref = np.exp(gaussian_filter(rng.normal(size=(768, 768)), 1) * 2 + 7).astype("uint16")
before = ref.copy()
before[384:, :384] = shift(ref[384:, :384], (12, 0), order=0, mode="nearest")
e = {
    "id": "SYNTHETIC_C001",
    "pixel_size_um": 0.17,
    "matched_canvas_verified": True,
    "mapping_evidence": "Synthetic shared grid; one quadrant has a known 12px displacement in the before cycle",
}
for k, arr in zip(
    ["before_reference", "before_cycle", "after_reference", "after_cycle"],
    [ref, before, ref, ref],
):
    f = a.out / (k + ".tif")
    tifffile.imwrite(f, arr)
    e[k] = {"path": str(f), "channel": 0}
m = a.out / "paired.json"
m.write_text(json.dumps([e], indent=2))
subprocess.run(
    [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/patch_qc.py"),
        "--manifest",
        str(m),
        "--out",
        str(a.out / "qc"),
    ],
    check=True,
)
print(a.out / "qc/SYNTHETIC_C001.png")

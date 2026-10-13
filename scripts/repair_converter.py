#!/usr/bin/env python3
"""Copy installed macsima2mc 1.3.1 and replace a removed NumPy alias locally."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
if importlib.metadata.version("macsima2mc") != "1.3.1":
    p.error("This narrow repair was inspected only for macsima2mc 1.3.1")
source = Path(importlib.util.find_spec("macsima2mc").origin).parent
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=False)
target = a.out / "macsima2mc"
shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
f = target / "tools.py"
original = f.read_text()
if original.count("np.row_stack(list_indices)") != 1:
    raise SystemExit("Unexpected source version; inspect before applying repair")
patched = original.replace("np.row_stack(list_indices)", "np.vstack(list_indices)")
f.write_text(patched)
entry = a.out / "macsima2mc_compat"
entry.write_text(
    "#!" + sys.executable + "\nfrom macsima2mc.stage import main\nmain()\n"
)
entry.chmod(0o755)
(a.out / "repair.json").write_text(
    json.dumps(
        dict(
            original_sha256=hashlib.sha256(original.encode()).hexdigest(),
            patched_sha256=hashlib.sha256(patched.encode()).hexdigest(),
            change="row_stack -> vstack",
            numpy=importlib.metadata.version("numpy"),
            converter="1.3.1",
        ),
        indent=2,
    )
)
print(entry)

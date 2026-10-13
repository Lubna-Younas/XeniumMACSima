# 03 — Convert MACSima tiles

Install macsima2mc in an isolated Python 3.12 environment using `environments/converter.txt`, then run `python -m pip check` and `macsima2mc --help`. Keep it separate from the pinned ASHLAR environment; do not upgrade NumPy inside an established scientific environment without checking compiled dependencies.

`stage_roi.py` accepts explicit raw/output paths, ROI, expected cycles and converter executable. It refuses an existing output directory. Initial-scan names are normalized through symbolic links without renaming sources. A pilot selects up to four central reference fields and the initial, first and last requested cycles.

```bash
/path/to/converter-env/bin/python scripts/stage_roi.py \
  --raw /path/to/experiment/RawData/R1/A1 \
  --out /path/to/new-run/ROI01_pilot --roi 1 --pilot \
  --cycles 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --converter /path/to/converter-env/bin/macsima2mc
```

The adapter uses highest exposures (`-he`) and acquisition tables (`-wt`), preserves DAPI in every acquisition and retains background/signal groups. It does not request flat-field correction. The source workflow is described by [macsima2mc](https://github.com/SchapiroLabor/macsima2mc).

The script requires channel coverage, matches every converted plane against the corresponding raw pixels and verifies stage coordinates. Ambiguous identical channels fail rather than guessing labels. An observed converter channel-label ordering mismatch is corrected only after pixel matching; source files are untouched. OME metadata is serialized as UTF-8 bytes because the tested BioFormats reader rejected numeric character entities for the micrometre unit.

`channel_manifest.json` and `markers.csv` preserve the actual concatenated channel order; alphabetical `C000`, `C001`, … ordering is explicit. BioFormats checks are a separate required gate before stitching. The adapter currently expects a single selected scan per cycle and a cycle-0 DAPI reference. Review other acquisition layouts before extending it.

## Compatibility repair for an existing NumPy 2 installation

macsima2mc 1.3.1 declares NumPy 1.26.4. An existing installation that was upgraded to NumPy 2 failed at `np.row_stack`. Prefer a correctly resolved isolated environment. For reproducing the targeted repair used in the source pilot:

```bash
/path/to/existing-converter-env/bin/python scripts/repair_converter.py \
  --out /path/to/new-private-converter-runtime
```

This copies the installed package and replaces the single inspected alias with `np.vstack`. It records hashes and versions and creates `macsima2mc_compat`; set `CONVERTER` to that executable. It does not modify the installation or certify unrelated dependency conflicts. This repair path needs its own real-data pilot. The public repository does not redistribute the copied upstream package.

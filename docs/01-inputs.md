# 01 — Check inputs and storage

Keep raw input read-only and write each attempt into a new run directory. Expected layout:

```text
/path/to/experiment/RawData/R1/A1/
  ROI1/
    initial-scan-directory/*.tif
    cycle-directory/*.tif
  ROI2/
  ...
```

The parser supports MACSima filenames containing `CYC`, `SCN`, `ST`, `F`, `D`, and `EXP` fields. Initial scans may omit `CYC`; they are recorded as cycle 0. Unsupported naming fails rather than silently dropping files.

```bash
.venv/bin/python scripts/inventory.py \
  --raw /path/to/experiment/RawData/R1/A1 \
  --rois 1 2 3 4 5 6 7 8 9 10 11 \
  --cycles 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --out /path/to/new-inventory
```

Inspect `inventory_receipt.json` and `inventory.csv`. The inventory reads every base-page header and segment bounds and decodes one representative plane in each ROI/cycle/scan/stage/channel/exposure group. It checks expected cycle presence, duplicate fields and unequal channel/exposure coverage. It cannot discover a tile missing from every channel without an independent acquisition plan. Compare field counts against vendor metadata as a separate review.

A successful sampled inventory is not an exhaustive image-integrity certificate. Conversion later compares every selected converted plane against source pixels.

## Storage gate

Use your account/project **quota**, including pending allocations and file-count limits. Filesystem free space alone is insufficient. Estimate raw-to-converted expansion, output mosaic dimensions, pyramid overhead, temporary files, concurrent ROIs, and any additional MACSiQ View copy. Keep a reserve. ASHLAR output dimensions can exceed initial estimates.

Create a private receipt after checking your site's quota tool:

```json
{
  "checked_unix": 0,
  "available_bytes": 0,
  "required_bytes": 0
}
```

Replace zeros with the measured timestamp and reviewed byte totals. The runner rejects insufficient or older-than-24-hour evidence; refresh it if the queue delay is long. This is an execution gate, not a live quota monitor. The example runs one ROI at a time. Do not delete another run's intermediates to satisfy the gate without reviewing their provenance and dependencies.

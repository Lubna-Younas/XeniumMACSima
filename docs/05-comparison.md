# 05 — Compare before and after on matched tissue

A lower flag count is meaningful only when the same tissue sites, cycle identity, reference choice, pixel scale and thresholds are compared. Crops and canvas origins can change between preprocessing methods.

1. Identify the reference DAPI and each cycle's stain DAPI using verified channel manifests. Background acquisitions are separate; do not accidentally substitute them for stain images.
2. Read image scale and OME positions, and inspect landmarks. Establish a common canvas for the before reference, before cycle, after reference and after cycle. Equal array shapes alone are insufficient.
3. If resampling is needed, write separate QC-only images. Record the reference-to-reference mapping, crop/origin conventions, interpolation and checks on held-out landmarks. Do not fit away a cycle's residual shift before measuring it.
4. Copy `config/paired_qc.example.json` to a private file. Add one entry per ROI/cycle, zero-based channel indices, input pixel size and a path/description of mapping evidence. Set `matched_canvas_verified` only after completing the preceding checks.
5. Run `patch_qc.py`. It additionally excludes sites whose before/after references do not match. Review paired-site counts and coverage exclusions with the flags.
6. Inspect representative flagged and unflagged regions at full resolution, including tile boundaries. Record whether the finding is displacement, seam, blur, tissue loss or uncertain.

The initial utility requires the mapping to be supplied. It does **not** automatically infer a safe transformation between arbitrary native and ASHLAR canvases. No example real-data improvement claim is bundled into this repository. A known-shift synthetic test establishes that the screening metric can detect a simple correction; it does not validate biological tissue or all stitching modes.

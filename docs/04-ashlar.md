# 04 — Batch stitching and cycle registration

ASHLAR aligns overlapping tiles into a mosaic and registers cycles using a shared channel. Here DAPI is verified as channel 0 in every converted acquisition. Tile positions provide initial geometry; image overlap drives refinement. The same cycle transformations are used across that acquisition's channels. See the [ASHLAR implementation](https://github.com/labsyspharm/ashlar) for algorithm details and limits.

Apply **`--flip-y` once, at ASHLAR**. This follows the [MACSima converter's orientation guidance](https://github.com/SchapiroLabor/macsima2mc#macsima2mc-and-ashlar); it is not a converter option in the tested version. Do not also flip source pixels without revisiting the coordinate convention.

The wrapper uses the installed [MCMICRO registration stage](https://mcmicro.org/parameters/) with ASHLAR 1.19.0, `--flip-y -m 30 --filter-sigma 1`, and no illumination or segmentation stage. These parameters reproduce the source pilot and remain subject to dataset-specific validation.

## Prepare the runtime

```bash
python3.12 -m venv /path/to/ashlar-env
/path/to/ashlar-env/bin/python -m pip install -r environments/ashlar.txt
/path/to/ashlar-env/bin/python -m pip check
/path/to/ashlar-env/bin/ashlar --version
cp config/cluster.example.env config/cluster.local.env
```

Fill in the private configuration. Supply Java 17 or later for Nextflow and a pinned local MCMICRO checkout. The source workflow used Nextflow 25.10.4. `config/mcmicro.config` runs tasks locally **inside the Slurm allocation**, disables containers and limits execution to the resources requested by the submission template. The Java module name is site-specific. Record the MCMICRO commit; do not silently track its latest development branch.

## Pilot and batch

After reviewing input and storage evidence:

```bash
bash scripts/submit.sh /absolute/path/to/config/cluster.local.env
```

The pilot uses ROI1, four selected tiles and initial/first/last cycles. The full batch defaults to ROI1–11, one task at a time. A Slurm `afterok` dependency and pilot receipts gate the full batch. A failed pilot prevents the dependent tasks from running. The submission directory prevents accidental duplicate submission. A new attempt needs a new run directory.

Resources are a starting template (8 CPUs, 64 GiB; pilot 1 hour, full ROI 24 hours). Benchmark and adjust them for your tile dimensions. The storage receipt must still be current when tasks start. This template does not install a scheduler monitor or retry failed tasks automatically.

## Validate completion

Inspect both `sacct` and `squeue`, then verify `staging_receipt.json`, `qc/bioformats_input_validation.json`, `qc/nextflow_trace.tsv` and `registration_receipt.json`. The checks require all input tiles/channels visible to BioFormats, consistent scale, uint16 output, expected channel count and plausible canvas extent. A canvas lower bound is a gross omission check, not a stitch-quality score. TIFF segment bounds are checked; output pixels are not exhaustively decoded by this receipt.

MCMICRO publishes a symlink to the output in its working directory to avoid duplicating large images. **Keep `nf_work` until outputs have been deliberately copied, checked and their links updated.** Scheduler success alone does not prove scientific correctness or MACSiQ View compatibility.

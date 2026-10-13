# Validation record and limits

## Foundation release

Six automated local tests passed with Python 3.10 and the versions in `environments/qc.txt`. The GitHub workflow targets Python 3.12 and has not yet run remotely. Automated local tests cover raw filename/coverage interpretation, missing cycles and duplicate acquisitions, a known patch displacement, a corrected synthetic pair, blank support and mismatched canvases. A mocked Slurm submission checks dependency wiring, preservation of the scripts path across Slurm spooling, and duplicate-submission refusal. A synthetic CLI run checks that CSV/JSON/PNG reports can be produced. Shell entry points are syntax checked. These tests use generated images and publish no biological data.

The production ancestor of the staging/registration scripts completed a small real-data pilot: four selected fields, initial/early/late cycles, 18 channels, BioFormats checks and successful MCMICRO registration. Its full multiplex batch was still running when this version was written. Do not reinterpret pilot success as full-cohort completion.

The generalized public Slurm runner has not been submitted against a new dataset. A fresh pilot is mandatory. Site-specific quota checks, resource requests and software installation must be validated locally. The optional macsima2mc compatibility patch fixes one inspected alias; it does not repair every potential dependency issue.

No full-resolution automatic correction, formal seam-acceptance criterion, Xenium transcript analysis, segmentation, biological annotation or MACSiQ View GUI validation is claimed by this release. Keep receipts and hashes with private runs; do not commit actual acquisition manifests or logs.

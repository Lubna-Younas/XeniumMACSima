# Maintaining this workflow

Use small, numbered additions with a clear stage and validation record. Work on `codex/` or other feature branches and review changes before integrating them. Separate tested behavior, pilot evidence, queued work and planned features.

Never commit data, tokens, cluster accounts, personal paths, patient metadata or actual run logs. Use example paths and synthetic tests. Preserve raw images and prior results. Avoid combining images with incompatible scales or coordinate systems.

Changes to plane ordering, coordinates, cropping, interpolation or thresholds need tests with a known expected outcome and a new real-data pilot before scaling. Document resource/storage implications and update the numbered guide. Do not silently change thresholds to make a before/after result look better.

Run `python -m unittest discover -s tests -v` in the QC environment, syntax-check all shell scripts and inspect the staged diff before publishing. Check dependencies in the environment where each command actually runs. Repository setup does not enable any recurring maintenance or cluster automation.

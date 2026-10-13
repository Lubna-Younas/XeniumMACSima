#!/usr/bin/env bash
set -euo pipefail
CONFIG=$(cd "$(dirname "${1:?Configuration required}")" && pwd)/$(basename "$1")
source "$CONFIG"
SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export WORKFLOW_SCRIPTS="$SCRIPTS"
: "${PARTITION:?}" "${RUN_ROOT:?}"
mkdir -p "$RUN_ROOT"
# Keep a durable submission guard: never silently submit a second batch.
mkdir "$RUN_ROOT/submission" || { echo 'Submission already exists; inspect it before retrying.' >&2; exit 1; }
PILOT=$(sbatch --export=ALL --parsable --job-name=macsima-pilot --partition="$PARTITION" --cpus-per-task=8 --mem=64G --time=01:00:00 \
  --output="$RUN_ROOT/submission/pilot_%j.log" "$SCRIPTS/run_roi.sh" "$CONFIG" 1 pilot)
printf '%s\n' "$PILOT" > "$RUN_ROOT/submission/pilot_job_id.txt"
BATCH=$(sbatch --export=ALL --parsable --job-name=macsima-batch --partition="$PARTITION" --cpus-per-task=8 --mem=64G --time=24:00:00 \
  --array="${ROI_ARRAY:-1-11%1}" --dependency="afterok:${PILOT%%;*}" --kill-on-invalid-dep=yes \
  --output="$RUN_ROOT/submission/roi_%A_%a.log" "$SCRIPTS/batch_task.sh" "$CONFIG")
printf '%s\n' "$BATCH" > "$RUN_ROOT/submission/batch_job_id.txt"
printf 'Pilot: %s\nBatch: %s\n' "$PILOT" "$BATCH"

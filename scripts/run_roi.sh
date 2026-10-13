#!/usr/bin/env bash
set -euo pipefail
CONFIG=${1:?Usage: run_roi.sh /absolute/config.env ROI [pilot|full]}
ROI=${2:?ROI required}
MODE=${3:-full}
source "$CONFIG"
: "${RAW_ROOT:?}" "${RUN_ROOT:?}" "${CONVERTER:?}" "${CONVERTER_PYTHON:?}" "${ASHLAR_ENV:?}" "${MCMICRO_SOURCE:?}" "${NEXTFLOW:?}"
[[ "$ROI" =~ ^[0-9]+$ && "$MODE" =~ ^(pilot|full)$ ]] || exit 2
SCRIPTS=${WORKFLOW_SCRIPTS:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
NAME=$(printf 'ROI%02d' "$ROI")
ARGS=()
if [[ "$MODE" == pilot ]]; then NAME="${NAME}_pilot"; ARGS+=(--pilot); fi
PROJECT="$RUN_ROOT/$NAME"
[[ ! -e "$PROJECT" ]] || { echo 'Use a fresh project directory; refusing stale outputs.' >&2; exit 1; }
[[ -f "$STORAGE_RECEIPT" ]] || { echo 'Missing reviewed storage receipt' >&2; exit 1; }
"$ASHLAR_ENV/bin/python" - "$STORAGE_RECEIPT" <<'PY'
import json,sys,time
s=json.load(open(sys.argv[1]))
if not(s['available_bytes'] >= s['required_bytes'] > 0 and 0 <= time.time()-s['checked_unix'] < 86400):
    raise SystemExit('Storage evidence insufficient or older than 24 hours; refresh before submission')
PY
unset PYTHONPATH PYTHONHOME
export PATH="$ASHLAR_ENV/bin:$PATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-8} MKL_NUM_THREADS=1 MPLBACKEND=Agg
"$CONVERTER_PYTHON" "$SCRIPTS/stage_roi.py" --raw "$RAW_ROOT" --out "$PROJECT" --roi "$ROI" --converter "$CONVERTER" --cycles "${CYCLES[@]}" "${ARGS[@]}"
"$ASHLAR_ENV/bin/python" "$SCRIPTS/validate_bioformats_inputs.py" "$PROJECT"
cd "$PROJECT"
git -C "$MCMICRO_SOURCE" rev-parse HEAD > qc/mcmicro_commit.txt
"$ASHLAR_ENV/bin/python" -m pip freeze > qc/ashlar_requirements.txt
"$CONVERTER_PYTHON" -m pip freeze > qc/converter_requirements.txt
"$NEXTFLOW" run "$MCMICRO_SOURCE" -profile cluster_ashlar -c "$SCRIPTS/../config/mcmicro.config" \
  --in "$PROJECT" --start-at registration --stop-at registration --illumination false \
  --ashlar-opts '--flip-y -m 30 --filter-sigma 1' -work-dir "$PROJECT/nf_work" \
  -with-trace "$PROJECT/qc/nextflow_trace.tsv" -with-report "$PROJECT/qc/nextflow_report.html"
"$ASHLAR_ENV/bin/python" "$SCRIPTS/verify_registration.py" "$PROJECT"

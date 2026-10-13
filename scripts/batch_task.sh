#!/usr/bin/env bash
set -euo pipefail
CONFIG=${1:?Configuration file required}
source "$CONFIG"
SCRIPTS=${WORKFLOW_SCRIPTS:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
"$ASHLAR_ENV/bin/python" - "$RUN_ROOT/ROI01_pilot" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);s=json.loads((p/'staging_receipt.json').read_text());r=json.loads((p/'registration_receipt.json').read_text())
if not(s['status']=='conversion_validated' and r['status']=='registered_requires_visual_QC' and r['input_pixel_mapping_validated'] and s['output_channels']==r['channels']):
    raise SystemExit('Pilot receipts failed')
PY
exec bash "$SCRIPTS/run_roi.sh" "$CONFIG" "${SLURM_ARRAY_TASK_ID:?}" full

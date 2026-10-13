import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy.ndimage import gaussian_filter, shift
import tifffile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import inventory
import patch_qc


def texture(n=384):
    rng = np.random.default_rng(82)
    return np.exp(gaussian_filter(rng.normal(size=(n, n)), 1) * 2 + 7).astype("uint16")


class WorkflowTests(unittest.TestCase):
    def test_slurm_submission_dependency_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            binary = d / "bin"
            binary.mkdir()
            stub = binary / "sbatch"
            stub.write_text(
                '#!/bin/bash\nprintf "%s\\n" "$WORKFLOW_SCRIPTS|$*" >> "$SUBMIT_LOG"\nif [[ "$*" == *afterok* ]]; then echo 102; else echo 101; fi\n'
            )
            stub.chmod(0o755)
            cfg = d / "cluster.env"
            cfg.write_text('PARTITION=test\nRUN_ROOT="' + str(d / "run") + '"\n')
            env = dict(
                os.environ,
                PATH=str(binary) + os.pathsep + os.environ["PATH"],
                SUBMIT_LOG=str(d / "submit.log"),
            )
            cmd = ["bash", str(ROOT / "scripts/submit.sh"), str(cfg)]
            subprocess.run(cmd, env=env, check=True, capture_output=True)
            logs = (d / "submit.log").read_text().splitlines()
            self.assertEqual(len(logs), 2)
            self.assertTrue(
                all(line.startswith(str(ROOT / "scripts") + "|") for line in logs)
            )
            self.assertIn("--dependency=afterok:101", logs[1])
            self.assertIn("--array=1-11%1", logs[1])
            self.assertNotEqual(
                subprocess.run(cmd, env=env, capture_output=True).returncode, 0
            )
            self.assertEqual(len((d / "submit.log").read_text().splitlines()), 2)

    def test_acquisition_names(self):
        r = inventory.acquisition(
            Path(
                "CYC-013_SCN-000_ST-S_R-1_W-A1_ROI-1_F-0004_A-CD31_C-Clone_D-PE_EXP-120.tif"
            )
        )
        self.assertEqual(
            (r["cycle"], r["field"], r["channel"], r["marker"], r["exposure"]),
            (13, "0004", "PE", "CD31", 120),
        )
        with self.assertRaises(ValueError):
            inventory.acquisition(Path("unrecognized.tif"))

    def test_missing_cycle_and_duplicate_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "ROI1"
            p.mkdir()
            name = "CYC-001_SCN-000_ST-S_R-1_W-A1_ROI-1_F-0001_A-DAPI_C-_D-DAPI_EXP-100.tif"
            xml = '<OME><Image><Pixels PhysicalSizeX="0.17" PhysicalSizeXUnit="um"/></Image></OME>'
            tifffile.imwrite(
                p / name, np.ones((32, 32), dtype="uint16"), description=xml
            )
            rows, errors = inventory.inspect(root, [1], [0, 1])
            self.assertEqual(len(rows), 1)
            self.assertTrue(errors)
            (p / "duplicate").mkdir()
            tifffile.imwrite(
                p / "duplicate" / name,
                np.ones((32, 32), dtype="uint16"),
                description=xml,
            )
            _, errors = inventory.inspect(root, [1], [1])
            self.assertTrue(
                any(e.get("error") == "Duplicate field acquisition" for e in errors)
            )

    def test_known_shift_and_corrected_pair(self):
        ref = texture()
        moved = shift(ref.astype(float), (12, 0), order=0, mode="nearest").astype(
            "uint16"
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, arr in enumerate([ref, moved, ref, ref]):
                p = Path(tmp) / f"{i}.tif"
                tifffile.imwrite(p, arr)
                paths.append(p)
            arrays = [patch_qc.overview(p, 0, 4) for p in paths]
            rows, _ = patch_qc.compare(arrays)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["before_displacement_flag"])
            self.assertAlmostEqual(rows[0]["before_shift_px"], 12, delta=1)
            self.assertFalse(rows[0]["after_joint_flag"])

    def test_blank_and_mismatched_support(self):
        zeros = np.zeros((192, 192), np.float32)
        rows, excluded = patch_qc.compare([zeros] * 4)
        self.assertFalse(rows)
        self.assertEqual(excluded, 4)
        with self.assertRaises(ValueError):
            patch_qc.compare([zeros, zeros[:100], zeros, zeros])

    def test_cli_and_mapping_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ref = texture()
            mov = shift(ref, (12, 0), mode="nearest")
            entry = {
                "id": "ROI01_C001",
                "pixel_size_um": 0.17,
                "matched_canvas_verified": True,
                "mapping_evidence": "Synthetic known shared grid",
            }
            for key, arr in zip(
                ["before_reference", "before_cycle", "after_reference", "after_cycle"],
                [ref, mov, ref, ref],
            ):
                path = d / (key + ".tif")
                tifffile.imwrite(path, arr)
                entry[key] = {"path": str(path), "channel": 0}
            manifest = d / "manifest.json"
            manifest.write_text(json.dumps([entry]))
            cmd = [
                sys.executable,
                str(ROOT / "scripts/patch_qc.py"),
                "--manifest",
                str(manifest),
                "--out",
                str(d / "qc"),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            summary = json.loads((d / "qc/summary.json").read_text())[0]
            self.assertEqual(summary["before_joint_flags"], 1)
            self.assertEqual(summary["after_joint_flags"], 0)
            self.assertTrue((d / "qc/ROI01_C001.png").stat().st_size > 1000)
            entry["matched_canvas_verified"] = False
            manifest.write_text(json.dumps([entry]))
            cmd[-1] = str(d / "rejected")
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()

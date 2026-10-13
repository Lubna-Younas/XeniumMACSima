#!/usr/bin/env python3
"""Read-only MACSima acquisition inventory. Header validation is not pixel QC."""
import argparse
import collections
import csv
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import tifffile


def acquisition(path):
    m = re.search(
        r"(?:CYC-(\d+)_)?SCN-(\d+)_ST-([^_]+).*_F-(\d+).*_D-(.*?)_EXP-(.*)\.tif$",
        path.name,
    )
    if not m:
        raise ValueError(f"Unrecognized acquisition filename: {path.name}")
    cycle, scan, stage, field, channel, exposure = m.groups()
    marker = re.search(r"_A-(.*?)_C-", path.name)
    clone = re.search(r"_C-(.*?)_D-", path.name)
    return dict(
        path=str(path.resolve()),
        cycle=int(cycle or 0),
        scan=scan,
        stage=stage,
        field=field,
        channel=channel,
        marker=marker[1] if marker else channel,
        clone=clone[1] if clone else "",
        exposure=float(exposure),
    )


def inspect(root, rois, cycles):
    rows, problems = [], []
    for roi in rois:
        files = sorted((root / f"ROI{roi}").rglob("*.tif"))
        found, groups, decoded = set(), collections.defaultdict(list), set()
        for path in files:
            try:
                r = acquisition(path)
                found.add(r["cycle"])
                r.update(roi=roi, bytes=path.stat().st_size)
                key = (r["cycle"], r["scan"], r["stage"], r["channel"], r["exposure"])
                with tifffile.TiffFile(path) as t:
                    page = t.pages[0]
                    if (
                        max(
                            o + n for o, n in zip(page.dataoffsets, page.databytecounts)
                        )
                        > r["bytes"]
                    ):
                        raise ValueError("TIFF segment extends beyond file")
                    r.update(
                        height=page.shape[-2],
                        width=page.shape[-1],
                        dtype=str(page.dtype),
                    )
                    px = ET.fromstring(page.description).find(".//{*}Pixels")
                    r.update(
                        pixel_size_x=px.get("PhysicalSizeX"),
                        pixel_unit=px.get("PhysicalSizeXUnit"),
                    )
                    r["representative_plane_decoded"] = key not in decoded
                    if key not in decoded:
                        page.asarray()
                        decoded.add(key)
                groups[key].append(r)
                rows.append(r)
            except Exception as e:
                problems.append(dict(roi=roi, file=path.name, error=str(e)))
        if found != set(cycles):
            problems.append(
                dict(roi=roi, expected_cycles=cycles, observed_cycles=sorted(found))
            )
        for key, group in groups.items():
            fields = [r["field"] for r in group]
            if len(set(fields)) != len(fields):
                problems.append(
                    dict(roi=roi, group=key, error="Duplicate field acquisition")
                )
        # Compare channel/exposure field sets within each cycle, scan and stage.
        by_stage = collections.defaultdict(list)
        for key, group in groups.items():
            by_stage[key[:3]].append({r["field"] for r in group})
        for key, sets in by_stage.items():
            if any(s != sets[0] for s in sets):
                problems.append(
                    dict(
                        roi=roi,
                        group=key,
                        error="Unequal field coverage across channels/exposures",
                    )
                )
    return rows, problems


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--raw", type=Path, required=True, help="Directory containing ROI1, ROI2, ..."
    )
    p.add_argument("--rois", nargs="+", type=int, required=True)
    p.add_argument(
        "--cycles", nargs="+", type=int, required=True, help="Include initial scan as 0"
    )
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    rows, problems = inspect(a.raw.resolve(), a.rois, a.cycles)
    if rows:
        with (a.out / "inventory.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    report = dict(
        passed=bool(rows) and not problems,
        files=len(rows),
        raw_bytes=sum(r["bytes"] for r in rows),
        problems=problems,
        validation="All base-page headers and segment bounds; one full plane decoded per acquisition group. Not exhaustive pixel validation.",
    )
    (a.out / "inventory_receipt.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

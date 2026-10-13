#!/usr/bin/env python3
"""Paired DAPI registration screening on explicitly matched image canvases."""
import argparse
import csv
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage
from skimage.registration import phase_cross_correlation
import tifffile


def highpass(a):
    a = np.log1p(a.astype(np.float32))
    return a - ndimage.gaussian_filter(a, 1)


def ncc(a, b):
    a, b = a.ravel(), b.ravel()
    denom = a.std() * b.std()
    return (
        float(np.mean((a - a.mean()) * (b - b.mean())) / denom) if denom > 0 else np.nan
    )


def metric(reference, cycle, step, max_shift_px=8, min_ncc=0.5):
    a, b = highpass(reference), highpass(cycle)
    shift = phase_cross_correlation(a, b, upsample_factor=10, normalization=None)[0]
    trim = max(2, a.shape[0] // 6)
    support = np.s_[trim:-trim, trim:-trim]
    fitted = ndimage.shift(b, shift, order=1, mode="constant", cval=np.nan)
    raw, fit = ncc(a[support], b[support]), ncc(a[support], fitted[support])
    confident = bool(
        np.isfinite(fit) and fit >= min_ncc and np.max(np.abs(shift)) <= trim - 2
    )
    magnitude = float(np.linalg.norm(shift) * step)
    return dict(
        ncc=raw,
        fit_ncc=fit,
        shift_px=magnitude,
        dy_px=float(shift[0] * step),
        dx_px=float(shift[1] * step),
        confident=confident,
        low_match_flag=bool(not np.isfinite(raw) or raw < min_ncc),
        displacement_flag=bool(confident and magnitude > max_shift_px),
        joint_flag=bool(
            not np.isfinite(raw)
            or raw < min_ncc
            or (confident and magnitude > max_shift_px)
        ),
    )


def overview(path, channel, step, max_decode_gib=1):
    """Area mean in row blocks; large compressed planes require a separate overview."""
    with tifffile.TiffFile(path) as t:
        if len(t.series) != 1:
            raise ValueError(
                "QC expects a stitched image with one series, not raw tiles"
            )
        pg = t.series[0].pages[channel]
        if len(pg.shape) != 2 or pg.dtype != np.dtype("uint16"):
            raise ValueError("QC currently supports 2D uint16 channel planes")
        if pg.is_memmappable:
            image = tifffile.memmap(path, page=pg.index, mode="r")
        elif np.prod(pg.shape) * pg.dtype.itemsize <= max_decode_gib * 2**30:
            image = pg.asarray()
        else:
            raise ValueError(
                "Compressed base plane exceeds decoding budget; supply an explicit overview and its pixel size"
            )
        h, w = (n // step * step for n in image.shape)
        out = np.empty((h // step, w // step), np.float32)
        for y in range(0, h, step * 128):
            block = np.asarray(image[y : min(h, y + step * 128), :w], dtype=np.float32)
            out[y // step : (y + len(block)) // step] = block.reshape(
                -1, step, w // step, step
            ).mean((1, 3))
        return out


def compare(arrays, step=4, patch=96, stride=96, max_shift_px=8, min_ncc=0.5):
    if len({a.shape for a in arrays}) != 1:
        raise ValueError(
            "Before/after reference and cycle must share an explicitly matched canvas"
        )
    rows, excluded = [], 0
    for y in range(0, arrays[0].shape[0] - patch + 1, stride):
        for x in range(0, arrays[0].shape[1] - patch + 1, stride):
            parts = [a[y : y + patch, x : x + patch] for a in arrays]
            if any((a > 0).mean() < 0.9 for a in parts) or any(
                highpass(parts[i]).std() < 0.10 for i in [0, 2]
            ):
                excluded += 1
                continue
            # Independent cross-reference check: reject mismatched before/after sites.
            if ncc(highpass(parts[0]), highpass(parts[2])) < min_ncc:
                excluded += 1
                continue
            row = dict(y_px=(y + patch / 2) * step, x_px=(x + patch / 2) * step)
            for side, r, c in [
                ("before", parts[0], parts[1]),
                ("after", parts[2], parts[3]),
            ]:
                row.update(
                    {
                        side + "_" + k: v
                        for k, v in metric(r, c, step, max_shift_px, min_ncc).items()
                    }
                )
            rows.append(row)
    return rows, excluded


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--step", type=int, default=4)
    p.add_argument("--patch", type=int, default=96, help="Size in downsampled pixels")
    p.add_argument("--stride", type=int, default=96)
    p.add_argument("--max-shift-px", type=float, default=8)
    p.add_argument("--min-ncc", type=float, default=0.5)
    a = p.parse_args()
    if (
        min(a.step, a.stride) < 1
        or a.patch < 24
        or not 0 < a.min_ncc <= 1
        or a.max_shift_px < 0
    ):
        p.error("Invalid sampling/threshold parameters")
    entries = json.loads(a.manifest.read_text())
    a.out.mkdir(parents=True, exist_ok=False)
    summary, identifiers = [], set()
    for e in entries:
        ident = e["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ident) or ident in identifiers:
            raise ValueError("Unique safe identifiers required")
        identifiers.add(ident)
        if e.get("matched_canvas_verified") is not True or not e.get(
            "mapping_evidence"
        ):
            raise ValueError(
                "Provide verified canvas mapping and its evidence before comparing flags"
            )
        pixel_um = float(e["pixel_size_um"])
        if not np.isfinite(pixel_um) or pixel_um <= 0:
            raise ValueError("Positive pixel size in micrometres required")
        keys = ["before_reference", "before_cycle", "after_reference", "after_cycle"]
        arrays = [overview(e[k]["path"], int(e[k]["channel"]), a.step) for k in keys]
        rows, excluded = compare(
            arrays, a.step, a.patch, a.stride, a.max_shift_px, a.min_ncc
        )
        result = dict(
            id=ident,
            paired_sites=len(rows),
            excluded_sites=excluded,
            status=(
                "screened_requires_visual_review" if rows else "insufficient_support"
            ),
            mapping_evidence=e["mapping_evidence"],
        )
        if rows:
            with (a.out / (ident + "_patches.csv")).open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        bg = np.log1p(arrays[0])
        lo, hi = np.percentile(bg, [5, 99])
        bg = 1 - 0.25 * np.clip((bg - lo) / max(float(hi - lo), 1e-6), 0, 1)
        for ax, side in zip(axes, ["before", "after"]):
            bad = [r for r in rows if r[side + "_joint_flag"]]
            result[side + "_joint_flags"] = len(bad)
            result[side + "_median_ncc"] = (
                float(
                    np.median(
                        [
                            r[side + "_ncc"]
                            for r in rows
                            if np.isfinite(r[side + "_ncc"])
                        ]
                    )
                )
                if any(np.isfinite(r[side + "_ncc"]) for r in rows)
                else None
            )
            ax.imshow(
                bg,
                cmap="gray",
                vmin=0,
                vmax=1,
                extent=(
                    0,
                    bg.shape[1] * a.step * pixel_um,
                    bg.shape[0] * a.step * pixel_um,
                    0,
                ),
            )
            ax.scatter(
                [r["x_px"] * pixel_um for r in bad],
                [r["y_px"] * pixel_um for r in bad],
                c="#df168c",
                s=9,
            )
            ax.set(
                title=f"{ident} {side}: {len(bad)} / {len(rows)} patch flags",
                xlabel="Reference x (µm)",
                ylabel="Reference y (µm)",
            )
        fig.suptitle(
            "Exploratory DAPI QC — flags are not confirmed registration defects"
        )
        fig.tight_layout()
        fig.savefig(a.out / (ident + ".png"), dpi=160)
        plt.close(fig)
        summary.append(result)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    (a.out / "method.json").write_text(
        json.dumps(
            dict(
                step=a.step,
                patch=a.patch,
                stride=a.stride,
                max_shift_px=a.max_shift_px,
                min_ncc=a.min_ncc,
                source_manifest=str(a.manifest.resolve()),
                limits="Paired supported sites only. Bleaching/tissue loss can produce flags. Repeated reference/cycle seams can escape detection. No correction applied.",
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

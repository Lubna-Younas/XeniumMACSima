if not __debug__:
    raise RuntimeError("Validation requires Python without optimization (-O)")

"""Stage original tiles via macsima2mc, validate saved plane/channel mapping, preserve provenance."""

from pathlib import Path
import argparse, collections, json, re, subprocess, time, xml.etree.ElementTree as ET
import numpy as np, tifffile

ET.register_namespace("", "http://www.openmicroscopy.org/Schemas/OME/2016-06")
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
P = argparse.ArgumentParser(description=__doc__)
P.add_argument("--roi", type=int, required=True)
P.add_argument(
    "--raw", type=Path, required=True, help="Directory containing ROI1, ROI2, ..."
)
P.add_argument("--out", type=Path, required=True, help="Fresh project directory")
P.add_argument(
    "--converter",
    required=True,
    help="Executable macsima2mc or isolated compatibility entry point",
)
P.add_argument(
    "--cycles",
    type=int,
    nargs="+",
    required=True,
    help="All expected cycles, including initial scan 0",
)
P.add_argument("--pilot", action="store_true")
a = P.parse_args()
if 0 not in a.cycles or len(set(a.cycles)) != len(a.cycles):
    P.error("Unique cycles including 0 required")
ROOT = a.raw.resolve()
OUT = a.out.resolve()
name = OUT.name
if OUT == ROOT or ROOT in OUT.parents:
    P.error("Output must be outside raw input")
OUT.mkdir(parents=True, exist_ok=False)
(OUT / "raw").mkdir()
(OUT / "qc").mkdir()
CONVERTER = str(Path(a.converter).resolve())
if not Path(CONVERTER).is_file():
    raise ValueError("Converter must be an executable file path")
state = {
    "expected_cycles": a.cycles,
    "roi": a.roi,
    "pilot": a.pilot,
    "status": "staging",
    "started": time.time(),
    "cycles": [],
}


def save():
    t = OUT / "staging_receipt.tmp"
    t.write_text(json.dumps(state, indent=2))
    t.replace(OUT / "staging_receipt.json")


save()


def parsed(p):
    n = p.name
    m = re.search(
        r"(?:CYC-(\d+)_)?SCN-(\d+)_ST-([^_]+).*_F-(\d+).*_D-(.*?)_EXP-(.*)\.tif$", n
    )
    if not m:
        raise ValueError(n)
    cy, scan, stage, field, ch, exp = m.groups()
    mark = re.search(r"_A-(.*?)_C-", n)
    clone = re.search(r"_C-(.*?)_D-", n)
    return dict(
        path=str(p),
        cycle=int(cy or 0),
        scan=scan,
        stage=stage,
        field=field,
        channel=ch,
        marker=mark[1] if mark else ch,
        clone=clone[1] if clone else "",
        exposure=float(exp),
    )


records = [parsed(p) for p in (ROOT / f"ROI{a.roi}").rglob("*.tif")]
keepfields = None
if {r["cycle"] for r in records} != set(a.cycles):
    raise ValueError("Observed cycles differ from --cycles")
if len({r["scan"] for r in records if r["cycle"] > 0}) > 1:
    raise ValueError(
        "Multiple scans per cycle require explicit selection before staging"
    )
if a.pilot:
    c0 = {r["field"]: r for r in records if r["cycle"] == 0 and r["channel"] == "DAPI"}
    pos = []
    for f, r in sorted(c0.items()):
        with tifffile.TiffFile(r["path"]) as t:
            st = ET.fromstring(t.pages[0].description).find(".//{*}StageLabel")
            pos.append((f, float(st.get("Y")), float(st.get("X"))))
    xy = np.array([p[1:] for p in pos])
    idx = np.argsort(((xy - np.median(xy, axis=0)) ** 2).sum(1))[:4]
    keepfields = {pos[i][0] for i in idx}
    records = [
        r
        for r in records
        if r["cycle"] in {0, min(c for c in a.cycles if c > 0), max(a.cycles)}
        and r["field"] in keepfields
    ]
    state["fields"] = sorted(keepfields)
# Source-plane mapping uses the maximum exposure within each acquisition/channel/tile.
selected = {}
for r in records:
    k = (r["cycle"], r["stage"], r["field"], r["channel"])
    if k not in selected or r["exposure"] > selected[k]["exposure"]:
        selected[k] = r
    if (
        k in selected
        and r is not selected[k]
        and r["exposure"] == selected[k]["exposure"]
    ):
        raise ValueError("Duplicate maximum exposure acquisition")
for cy in sorted({r["cycle"] for r in records}):
    group = [r for r in records if r["cycle"] == cy]
    links = OUT / f"converter_inputs/C{cy:03d}"
    links.mkdir(parents=True, exist_ok=True)
    for r in group:
        src = Path(r["path"])
        n = src.name
        if cy == 0:
            n = "CYC-000_" + n if not n.startswith("CYC-") else n
            if "_A-" not in n:
                n = n.replace("_D-", f'_A-{r["marker"]}_C-_D-', 1)
        dest = links / n
        if dest.is_symlink():
            assert dest.resolve() == src.resolve()
        elif dest.exists():
            raise RuntimeError("Unexpected existing staging input")
        else:
            dest.symlink_to(src)
    # Refuse channel gaps so converter cannot silently pad missing source channels.
    for stage in sorted({r["stage"] for r in group}):
        rows = [
            r for r in selected.values() if r["cycle"] == cy and r["stage"] == stage
        ]
        channels = {r["channel"] for r in rows}
        fields = {r["field"] for r in rows}
        assert "DAPI" in channels
        assert len(rows) == len(channels) * len(fields), (
            "Missing source planes",
            cy,
            stage,
        )
        assert all(
            {r["channel"] for r in rows if r["field"] == f} == channels for f in fields
        )
    done = OUT / f"qc/C{cy:03d}_converted.json"
    if not done.exists():
        log = OUT / f"qc/converter_C{cy:03d}.log"
        cmd = [CONVERTER, "-i", str(links), "-o", str(OUT / "converted"), "-he", "-wt"]
        with log.open("w") as stream:
            subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, check=True)
        done.write_text(
            json.dumps({"cycle": cy, "command": cmd, "completed": time.time()})
        )
    state["cycles"].append(cy)
    save()
    print("CONVERTED", name, cy, flush=True)
# Verify every converted tile plane against its original source pixels.
manifest = []
checks = []
for p in sorted((OUT / "converted").rglob("*.ome.tiff")):
    m = re.search(r"cycle-(\d+)-src-(.*?)-rack-", p.name)
    cy, stage = int(m[1]), m[2]
    rows = [r for r in selected.values() if r["cycle"] == cy and r["stage"] == stage]
    fields = sorted({r["field"] for r in rows})
    bykey = {(r["field"], r["marker"], r["channel"]): r for r in rows}
    with tifffile.TiffFile(p) as t:
        root = ET.fromstring(t.ome_metadata)
        images = root.findall("{*}Image")
        assert len(images) == len(fields)
        mapping = []
        for ti, (field, img) in enumerate(zip(fields, images)):
            pix = img.find("{*}Pixels")
            channels = pix.findall("{*}Channel")
            planes = pix.findall("{*}Plane")
            assert len(channels) == int(pix.get("SizeC"))
            # Match channels using saved metadata and ultimately source pixels; no filename order assumptions.
            tilemap = []
            for ci, ch in enumerate(channels):
                idx = int(pix.findall("{*}TiffData")[ci].get("IFD"))
                page = t.pages[idx]
                arr = page.asarray()
                candidates = (
                    [bykey[(field, *mapping[ci])]]
                    if mapping
                    else [r for r in rows if r["field"] == field]
                )
                matches = []
                for r in candidates:
                    with tifffile.TiffFile(r["path"]) as st:
                        raw = st.pages[0].asarray()
                    # Full plane equality ensures converter did not drop, zero-fill or reorder a channel.
                    if np.array_equal(arr, raw):
                        matches.append(r)
                assert len(matches) == 1, (
                    "Ambiguous or corrupted staged channel",
                    p,
                    field,
                    ci,
                    ch.attrib,
                )
                r = matches[0]
                tilemap.append((r["marker"], r["channel"]))
                pl = planes[ci]
                with tifffile.TiffFile(r["path"]) as st:
                    sr = ET.fromstring(st.pages[0].description)
                    sp = sr.find(".//{*}StageLabel")
                for dim in ["X", "Y"]:
                    units = {"mm": 1000.0, "µm": 1.0, "um": 1.0, "nm": 0.001, "m": 1e6}
                    assert np.isclose(
                        float(pl.get("Position" + dim))
                        * units[pl.get("Position" + dim + "Unit")],
                        float(sp.get(dim)) * units[sp.get(dim + "Unit")],
                    ), ("Stage position changed", p, field)
                # The converter writes correctly ordered pixels but reconstructs metadata from an unsorted group.
                # Rebind channel metadata to the source plane that was verified byte-for-byte.
                rawch = sr.find(".//{*}Channel")
                ch.set("ID", f"Channel:{ti}:{ci}")
                ch.set("Name", r["marker"])
                for attr in [
                    "EmissionWavelength",
                    "EmissionWavelengthUnit",
                    "ExcitationWavelength",
                    "ExcitationWavelengthUnit",
                ]:
                    if rawch.get(attr) is not None:
                        ch.set(attr, rawch.get(attr))
                sm = {v.get("K"): v.text for v in sr.findall(".//{*}M")}
                pl.set("ExposureTime", sm.get("ExposureTime") or str(r["exposure"]))
                pl.set("ExposureTimeUnit", sm.get("ExposureTimeUnit") or "ms")
                checks.append(
                    {
                        "cycle": cy,
                        "stage": stage,
                        "field": field,
                        "channel_index": ci,
                        "marker": r["marker"],
                        "filter": r["channel"],
                        "full_plane_equal": True,
                    }
                )
            assert tilemap[0][1] == "DAPI"
            assert len(set(tilemap)) == len(tilemap)
            assert set(tilemap) == {
                (r["marker"], r["channel"]) for r in rows if r["field"] == field
            }, ("Converter omitted a source channel", p, field)
            if not mapping:
                mapping = tilemap
            else:
                assert mapping == tilemap
        outname = f"C{cy:03d}_{stage}.ome.tif"
        dest = OUT / "raw" / outname
        if not dest.exists():
            dest.symlink_to(p)
        manifest.append(
            {
                "file": outname,
                "cycle": cy,
                "stage": stage,
                "channels": [
                    {
                        "marker": mk,
                        "filter": ch,
                        "source": next(
                            r["path"]
                            for r in rows
                            if r["marker"] == mk and r["channel"] == ch
                        ),
                    }
                    for mk, ch in mapping
                ],
                "tiles": len(fields),
                "converted_path": str(p),
            }
        )
    # Store corrected channel labels/exposure metadata; original source TIFFs are never changed.
    tifffile.tiffcomment(p, ET.tostring(root, encoding="utf-8"))
# MCMICRO sorts raw filenames alphabetically; this is the exact final channel order.
manifest.sort(key=lambda x: x["file"])
expected = {(r["cycle"], r["stage"]) for r in records}
assert {(x["cycle"], x["stage"]) for x in manifest} == expected
assert manifest[0]["cycle"] == 0
(OUT / "channel_manifest.json").write_text(json.dumps(manifest, indent=2))
(OUT / "source_manifest.json").write_text(json.dumps(records, indent=2))
(OUT / "qc/conversion_pixel_validation.json").write_text(json.dumps(checks, indent=2))
import csv

with (OUT / "markers.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["marker_name", "cycle", "stage", "filter"])
    w.writerows(
        [
            [c["marker"], g["cycle"], g["stage"], c["filter"]]
            for g in manifest
            for c in g["channels"]
        ]
    )
state.update(
    status="conversion_validated",
    finished=time.time(),
    ome_groups=len(manifest),
    output_channels=sum(len(x["channels"]) for x in manifest),
    validated_tile_planes=len(checks),
)
save()
print("STAGING_VALIDATED", name, len(manifest), flush=True)

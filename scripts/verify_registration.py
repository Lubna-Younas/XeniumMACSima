if not __debug__:
    raise RuntimeError("Validation requires Python without optimization (-O)")

from pathlib import Path
import sys, json, time, xml.etree.ElementTree as ET
import tifffile, numpy as np

p = Path(sys.argv[1])
m = json.loads((p / "channel_manifest.json").read_text())
files = list((p / "registration").glob("*.ome.tif"))
assert len(files) == 1, files
v = json.loads((p / "qc/bioformats_input_validation.json").read_text())
assert v["passed"]
expected = np.asarray(v["groups"][0]["expected_canvas_yx"])
with tifffile.TiffFile(files[0]) as t:
    s = t.series[0]
    assert np.all(np.asarray(s.shape[-2:]) >= expected * 0.8), (
        "Incomplete mosaic canvas",
        s.shape,
        expected,
    )
    n = sum(len(g["channels"]) for g in m)
    assert (s.shape[0] if s.ndim == 3 else 1) == n, (s.shape, n)
    assert s.dtype == np.dtype("uint16")
    root = ET.fromstring(t.ome_metadata)
    px = root.find(".//{*}Pixels")
    assert (
        np.isclose(float(px.get("PhysicalSizeX")), v["groups"][0]["pixel_size_um"])
        and px.get("PhysicalSizeXUnit") == "µm"
    )
    for axis in ["X", "Y"]:
        assert (
            np.isclose(
                float(px.get("PhysicalSize" + axis)), v["groups"][0]["pixel_size_um"]
            )
            and px.get("PhysicalSize" + axis + "Unit") == "µm"
        )
    for pg in t.pages:
        assert (
            max(o + n for o, n in zip(pg.dataoffsets, pg.databytecounts))
            <= files[0].stat().st_size
        )
    result = {
        "status": "registered_requires_visual_QC",
        "finished": time.time(),
        "file": str(files[0]),
        "shape": list(s.shape),
        "channels": n,
        "levels": len(s.levels),
        "pixel_size_um": v["groups"][0]["pixel_size_um"],
        "cycles": sorted({g["cycle"] for g in m}),
        "flip_y": True,
        "mcmicro_trace": str(p / "qc/nextflow_trace.tsv"),
        "input_pixel_mapping_validated": True,
    }
(p / "registration_receipt.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result), flush=True)

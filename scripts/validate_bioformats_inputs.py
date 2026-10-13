if not __debug__:
    raise RuntimeError("Validation requires Python without optimization (-O)")

"""Require ASHLAR to see all tiles, channels and physical coordinates."""

from pathlib import Path
import sys, json, xml.etree.ElementTree as ET
import numpy as np, tifffile
from ashlar import reg

p = Path(sys.argv[1])
results = []
for g in json.loads((p / "channel_manifest.json").read_text()):
    r = reg.BioformatsReader(str(p / "raw" / g["file"]))
    m = r.metadata
    assert m.num_images == g["tiles"], (g["file"], m.num_images, g["tiles"])
    assert m.num_channels == len(g["channels"]), (g["file"], m.num_channels)
    with tifffile.TiffFile(p / "raw" / g["file"]) as tf:
        px = ET.fromstring(tf.ome_metadata).find(".//{*}Pixels")
        units = {"mm": 1000.0, "µm": 1.0, "um": 1.0, "nm": 0.001}
        expected_pixel = (
            float(px.get("PhysicalSizeX")) * units[px.get("PhysicalSizeXUnit")]
        )
    assert np.isclose(m.pixel_size, expected_pixel), (
        g["file"],
        m.pixel_size,
        expected_pixel,
    )
    positions = np.asarray(m.positions)
    size = np.asarray(m.size)
    assert np.isfinite(positions).all()
    with tifffile.TiffFile(p / "raw" / g["file"]) as t:
        assert np.array_equal(r.read(series=0, c=0), t.pages[0].asarray()), g["file"]
    span = np.ptp(positions, axis=0) + size
    results.append(
        {
            "file": g["file"],
            "tiles": m.num_images,
            "channels": m.num_channels,
            "pixel_size_um": m.pixel_size,
            "expected_canvas_yx": span.tolist(),
        }
    )
(p / "qc/bioformats_input_validation.json").write_text(
    json.dumps({"passed": True, "groups": results}, indent=2)
)
print("BIOFORMATS_INPUTS_VALIDATED", len(results), flush=True)

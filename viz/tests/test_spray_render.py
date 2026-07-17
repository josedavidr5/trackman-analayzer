import pandas as pd
from core.hitting import spray_points
from viz import spray_render as sp


def _pts():
    df = pd.DataFrame({
        "ExitSpeed": [98, 104, 80, 95], "Angle": [12, 28, -5, 20],
        "Distance": [150, 410, 60, 330], "Bearing": [0, 10, -20, 25],
        "PlayResult": ["1B", "HR", "Out", "2B"], "PitchCall": ["InPlay"] * 4,
    })
    return spray_points(df)


def test_render_spray_png_ev_and_result():
    pts = _pts()
    for cb in ("ev", "result"):
        png = sp.render_spray_png(pts, "A", color_by=cb)
        assert isinstance(png, (bytes, bytearray)) and png[:8].startswith(b"\x89PNG")


def test_render_spray_png_empty():
    assert sp.render_spray_png({"points": []}, "A") is None

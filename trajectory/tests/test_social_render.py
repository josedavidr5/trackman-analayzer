import pandas as pd
from trajectory import social_render as sr


def _rows():
    return pd.DataFrame({
        "TaggedPitchType": ["Fastball", "Slider"],
        "RelSpeed": [94.0, 84.0], "SpinRate": [2300, 2500],
        "RelSide": [-1.8, -1.7], "RelHeight": [5.9, 5.8], "Extension": [6.5, 6.4],
        "InducedVertBreak": [16.0, 2.0], "HorzBreak": [-8.0, 7.0],
        "PlateLocSide": [0.2, -0.3], "PlateLocHeight": [2.8, 2.1],
    })


def test_render_trajectories_png_night_returns_bytes_and_metas():
    png, metas = sr.render_trajectories_png(_rows(), pitcher="P", night=True)
    assert isinstance(png, (bytes, bytearray)) and png[:8].startswith(b"\x89PNG")
    assert len(metas) == 2


def test_render_trajectories_png_day_also_works():
    png, metas = sr.render_trajectories_png(_rows(), pitcher="P", night=False)
    assert isinstance(png, (bytes, bytearray)) and len(png) > 1000


def test_render_trajectories_png_empty():
    png, metas = sr.render_trajectories_png(pd.DataFrame({"TaggedPitchType": []}))
    assert png is None and metas == []


def _thrown_rows():
    return pd.DataFrame({
        "TaggedPitchType": ["Fastball", "Slider", "Sinker"],
        "PlateLocSide": [0.1, -0.4, 0.6], "PlateLocHeight": [2.6, 2.0, 3.1],
        "RelSpeed": [94, 84, 92], "SpinRate": [2300, 2500, 2100],
        "InducedVertBreak": [16, 2, 10], "HorzBreak": [-8, 7, -10],
        "PlayResult": ["K", "Out", "1B"],
    })


def test_render_pitches_thrown_png_night_returns_bytes_and_count():
    png, n = sr.render_pitches_thrown_png(_thrown_rows(), pitcher="P", night=True)
    assert isinstance(png, (bytes, bytearray)) and png[:8].startswith(b"\x89PNG")
    assert n == 3


def test_render_pitches_thrown_png_missing_cols():
    png, n = sr.render_pitches_thrown_png(pd.DataFrame({"TaggedPitchType": ["FB"]}))
    assert png is None and n == 0

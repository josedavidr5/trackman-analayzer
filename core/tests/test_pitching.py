import numpy as np
import pandas as pd
import pytest
from core.pitching import (pitch_summary, pitch_discipline, arsenal_stuff, movement_points)

def _df():
    # 4 sliders: 1 StrikeCalled, 1 StrikeSwinging, 1 FoulBall, 1 BallCalled
    return pd.DataFrame({
        "TaggedPitchType": ["Slider"] * 4 + ["Fastball"] * 2,
        "PitchCall": ["StrikeCalled", "StrikeSwinging", "FoulBall", "BallCalled",
                      "InPlay", "StrikeSwinging"],
        "RelSpeed": [84, 85, 84, 86, 94, 95],
        "SpinRate": [2400, 2410, 2390, 2405, 2200, 2210],
        "HorzBreak": [6, 7, 6.5, 6, -8, -8.5],
        "InducedVertBreak": [2, 2.5, 2.2, 2.1, 16, 16.5],
        "PlateLocSide": [0.1, 0.2, 0.0, 1.6, -0.1, 0.0],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.5, 2.5, 2.4],
    })

def test_csw_pct_slider():
    stuff = arsenal_stuff(_df())
    row = stuff[stuff["Pitch"] == "Slider"].iloc[0]
    # CSW = (StrikeCalled + StrikeSwinging) / 4 = 2/4 = 50.0
    assert row["CSW %"] == 50.0

def test_whiff_pct_slider():
    stuff = arsenal_stuff(_df())
    row = stuff[stuff["Pitch"] == "Slider"].iloc[0]
    # swings = StrikeSwinging + FoulBall + InPlay = 2; whiffs = 1 → 50.0
    assert row["Whiff %"] == 50.0

def test_arsenal_stuff_shape():
    stuff = arsenal_stuff(_df())
    assert set(stuff["Pitch"]) == {"Slider", "Fastball"}
    for c in ["Usage %", "Avg mph", "IVB", "HB", "Whiff %", "CSW %"]:
        assert c in stuff.columns

def test_movement_points_centroid():
    mp = movement_points(_df())
    cents = {c["pitch_type"]: c for c in mp["centroids"]}
    assert cents["Fastball"]["hb"] == pytest.approx(-8.25)
    assert cents["Fastball"]["ivb"] == pytest.approx(16.25)
    assert cents["Slider"]["n"] == 4
    assert sum(c["usage"] for c in mp["centroids"]) == pytest.approx(100.0, abs=0.2)

def test_empty_inputs_dont_crash():
    empty = pd.DataFrame({"TaggedPitchType": []})
    assert arsenal_stuff(empty).empty
    assert movement_points(empty) == {"pitches": [], "centroids": []}

def test_regression_matches_monolith_summary():
    # pitch_summary debe igualar el cálculo directo por grupos
    df = _df()
    summ = pitch_summary(df)
    fb = summ[summ["Pitch"] == "Fastball"].iloc[0]
    assert fb["Count"] == 2
    assert fb["Usage %"] == round(100 * 2 / 6, 1)
    assert fb["Avg mph"] == 94.5

from core.pitching import whiff_csw_zone_grid

def _cell(grid, ix, iz):
    return next(c for c in grid["cells"] if c["ix"] == ix and c["iz"] == iz)

def test_zone_grid_center_cell_rates():
    # Celda central (ix=2, iz=2): x∈[-0.277,0.277], z∈[2.167,2.833] → usar x=0, z=2.5
    df = pd.DataFrame({
        "PlateLocSide":  [0.0, 0.0, 0.0, 0.0],
        "PlateLocHeight":[2.5, 2.5, 2.5, 2.5],
        "PitchCall": ["StrikeSwinging", "StrikeSwinging", "FoulBall", "StrikeCalled"],
    })
    grid = whiff_csw_zone_grid(df)
    c = _cell(grid, 2, 2)
    assert c["n_pitches"] == 4
    assert c["n_swings"] == 3          # 2 StrikeSwinging + 1 FoulBall
    assert c["whiffs"] == 2
    assert c["called"] == 1
    assert c["whiff_pct"] == round(100 * 2 / 3, 1)      # whiffs/swings
    assert c["csw_pct"] == round(100 * (1 + 2) / 4, 1)  # (called+whiffs)/pitches

def test_zone_grid_reliability_flags():
    # 1 solo swing en una celda → whiff no confiable; <5 pitcheos → csw no confiable
    df = pd.DataFrame({
        "PlateLocSide": [0.0], "PlateLocHeight": [2.5],
        "PitchCall": ["StrikeSwinging"],
    })
    c = _cell(whiff_csw_zone_grid(df), 2, 2)
    assert c["whiff_reliable"] is False   # 1 swing < 4
    assert c["csw_reliable"] is False     # 1 pitch < 5

def test_zone_grid_outer_clamp():
    # Pitcheo muy afuera a la derecha (x=3.0) cae en la columna de borde ix=4;
    # muy abajo (z=0.2) cae en iz=0.
    df = pd.DataFrame({
        "PlateLocSide": [3.0], "PlateLocHeight": [0.2],
        "PitchCall": ["BallCalled"],
    })
    c = _cell(whiff_csw_zone_grid(df), 4, 0)
    assert c["n_pitches"] == 1

def test_zone_grid_inner_3x3_is_strike_zone():
    from core.metrics import ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP
    grid = whiff_csw_zone_grid(pd.DataFrame({"PlateLocSide": [], "PlateLocHeight": [], "PitchCall": []}))
    # bordes internos coinciden con la zona
    assert grid["x_edges"][1] == -ZONE_HALF_WIDTH
    assert grid["x_edges"][4] == ZONE_HALF_WIDTH
    assert grid["z_edges"][1] == ZONE_BOTTOM
    assert grid["z_edges"][4] == ZONE_TOP

def test_zone_grid_missing_columns_no_raise():
    assert whiff_csw_zone_grid(pd.DataFrame({"PlateLocSide": [0.0]}))["cells"] == []
    assert whiff_csw_zone_grid(pd.DataFrame())["cells"] == []

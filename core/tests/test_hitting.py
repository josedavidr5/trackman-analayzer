import numpy as np
import pandas as pd
import pytest
from core.hitting import (spray_points, hitting_summary, build_split_table,
                          build_play_result_table)


def _bb():
    return pd.DataFrame({
        "Batter": ["A"] * 5,
        "PitchCall": ["InPlay"] * 5,
        "PlayResult": ["1B", "HR", "Out", "2B", "Out"],
        "ExitSpeed": [98.0, 104.0, 80.0, 95.0, 88.0],
        "Angle": [12.0, 28.0, -5.0, 20.0, 45.0],
        "Distance": [150.0, 410.0, 60.0, 330.0, 120.0],
        "Bearing": [0.0, 10.0, -20.0, 25.0, -35.0],
        "PitcherThrows": ["R", "R", "L", "R", "L"],
    })


def test_spray_points_xy():
    pts = spray_points(_bb())["points"]
    assert len(pts) == 5
    p0 = pts[0]
    assert p0["x"] == pytest.approx(0.0, abs=1e-6)
    assert p0["y"] == pytest.approx(150.0)
    assert p0["result"] == "1B" and p0["ev"] == 98.0


def test_spray_points_missing_cols():
    assert spray_points(pd.DataFrame({"ExitSpeed": [90.0]}))["points"] == []


def test_hitting_summary_metrics():
    s = hitting_summary(_bb(), {"ev_hard": 95, "barrel_ev": 98})
    assert s["n"] == 5
    assert s["max_ev"] == 104.0
    assert s["avg_ev"] == pytest.approx(np.mean([98, 104, 80, 95, 88]))
    assert s["hh_pct"] == 60.0


def test_build_split_table_by_hand():
    t = build_split_table(_bb(), ev_hard=95)
    assert set(t["vs"]) == {"R", "L"}


def test_build_play_result_table():
    t = build_play_result_table(_bb())
    assert "Result" in t.columns and int(t["Count"].sum()) == 5

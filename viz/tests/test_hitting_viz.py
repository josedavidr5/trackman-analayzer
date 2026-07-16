import plotly.graph_objects as go
import pandas as pd
from viz import hitting as vh


def _bb():
    return pd.DataFrame({
        "ExitSpeed": [98, 104, 80, 95, 88, 101, 76], "Angle": [12, 28, -5, 20, 45, 15, 60],
        "PlateLocSide": [0.1, -0.2, 0.3, 0.0, 0.4, -0.1, 0.2],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.1, 3.0, 2.2, 2.5],
        "PlayResult": ["1B", "HR", "Out", "2B", "Out", "1B", "Out"],
        "PitchCall": ["InPlay"] * 7, "Date": pd.to_datetime(["2026-06-01"] * 7),
    })


def test_builders_return_figures_and_empty():
    for fn in (vh.ev_distribution, vh.la_distribution, vh.ev_la_scatter, vh.damage_zone, vh.rolling_ev):
        assert isinstance(fn(_bb(), "A"), go.Figure)
        f = fn(pd.DataFrame(), "A")
        assert isinstance(f, go.Figure) and f.layout.annotations


def test_spray_interactive():
    from core.hitting import spray_points
    df = pd.DataFrame({"Distance": [150, 410], "Bearing": [0, 10], "ExitSpeed": [98, 104],
                       "Angle": [12, 28], "PlayResult": ["1B", "HR"], "PitchCall": ["InPlay"] * 2})
    pts = spray_points(df)
    assert isinstance(vh.spray_interactive(pts, "A", color_by="ev"), go.Figure)
    assert isinstance(vh.spray_interactive(pts, "A", color_by="result"), go.Figure)
    assert isinstance(vh.spray_interactive({"points": []}, "A"), go.Figure)

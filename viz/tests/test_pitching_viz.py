import plotly.graph_objects as go
import pandas as pd
from core.pitching import movement_points
from viz import pitching as vp


def _pts():
    df = pd.DataFrame({
        "TaggedPitchType": ["Slider", "Slider", "Fastball", "Fastball"],
        "PitchCall": ["StrikeSwinging", "FoulBall", "InPlay", "StrikeCalled"],
        "RelSpeed": [84, 85, 94, 95], "SpinRate": [2400, 2410, 2200, 2210],
        "HorzBreak": [6, 7, -8, -9], "InducedVertBreak": [2, 3, 16, 17],
    })
    return movement_points(df)


def test_movement_bubble_returns_figure():
    fig = vp.movement_bubble(_pts(), "Test Pitcher")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    # Stronger assertions: centroid bubbles carry pitch-type label
    assert any(getattr(t, "text", None) for t in fig.data)


def test_movement_bubble_empty():
    fig = vp.movement_bubble({"pitches": [], "centroids": []}, "X")
    assert isinstance(fig, go.Figure)
    # Stronger assertions: degraded to empty-state figure
    assert len(fig.data) == 0
    assert fig.layout.annotations

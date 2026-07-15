import plotly.graph_objects as go
import pandas as pd
from core.pitching import movement_points, build_usage_by_count
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


def _loc_df():
    return pd.DataFrame({
        "TaggedPitchType": ["Slider"] * 6 + ["Fastball"] * 6,
        "PlateLocSide": [0.1, -0.2, 0.3, 0.0, 0.5, -0.1, 0.2, -0.3, 0.1, 0.0, 0.4, -0.2],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.1, 3.0, 2.2, 2.5, 2.7, 2.3, 2.9, 2.4, 2.6],
        "RelSpeed": [84, 85, 84, 86, 83, 85, 94, 95, 93, 96, 94, 95],
    })


def test_location_scatter_ok_and_empty():
    # Non-empty case
    fig = vp.location_scatter(_loc_df(), "P")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    # Empty case
    fig_empty = vp.location_scatter(pd.DataFrame(), "P")
    assert isinstance(fig_empty, go.Figure)
    assert fig_empty.layout.annotations


def test_hot_zone_ok_and_sparse():
    # Non-empty case
    fig = vp.hot_zone(_loc_df(), "P")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    # Sparse case
    fig_sparse = vp.hot_zone(_loc_df().head(3), "P")
    assert isinstance(fig_sparse, go.Figure)
    assert fig_sparse.layout.annotations


def test_location_by_pitch_ok_and_empty():
    # Non-empty case
    fig = vp.location_by_pitch(_loc_df(), "P")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    # Empty case
    fig_empty = vp.location_by_pitch(pd.DataFrame(), "P")
    assert isinstance(fig_empty, go.Figure)
    assert fig_empty.layout.annotations


def test_location_builders_missing_pitchtype_degrade():
    # PlateLoc present but no TaggedPitchType column → must degrade, not raise
    df = pd.DataFrame({"PlateLocSide": [0.1, -0.2], "PlateLocHeight": [2.5, 2.4]})
    f1 = vp.location_scatter(df, "P")
    f2 = vp.location_by_pitch(df, "P")
    assert f1.layout.annotations and f2.layout.annotations


def test_velo_trend_ok_and_empty():
    df = pd.DataFrame({
        "TaggedPitchType": ["Slider", "Slider", "Fastball"],
        "RelSpeed": [84, 85, 94],
        "Date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-01"]),
    })
    # Non-empty case
    fig = vp.velo_trend(df, "P")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    # Empty case
    fig_empty = vp.velo_trend(pd.DataFrame(), "P")
    assert isinstance(fig_empty, go.Figure)
    assert fig_empty.layout.annotations


def test_usage_heatmap_ok_and_empty():
    df = pd.DataFrame({"TaggedPitchType": ["Slider", "Fastball", "Slider"],
                       "Count": ["0-0", "0-0", "1-1"]})
    tab = build_usage_by_count(df)
    # Non-empty case
    fig = vp.usage_heatmap(tab, "P")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    # Empty case
    fig_empty = vp.usage_heatmap(pd.DataFrame(), "P")
    assert isinstance(fig_empty, go.Figure)
    assert fig_empty.layout.annotations

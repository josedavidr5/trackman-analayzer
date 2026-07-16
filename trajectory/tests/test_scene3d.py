import plotly.graph_objects as go
from trajectory import scene3d


def test_field_scene_traces_nonempty():
    tr = scene3d.field_scene_traces()
    assert isinstance(tr, list) and len(tr) >= 8
    assert all(isinstance(x, (go.Scatter3d, go.Mesh3d)) for x in tr)


def test_catcher_layout_has_camera_and_aspect():
    lay = scene3d.catcher_scene_layout("t")
    assert "camera" in lay["scene"]
    assert lay["scene"]["aspectratio"]["y"] != lay["scene"]["aspectratio"]["x"]
    # catcher view: eye detrás del plato (y negativo en coords normalizadas)
    assert lay["scene"]["camera"]["eye"]["y"] < 0


def test_pt_color_known_and_fallback():
    assert scene3d.pt_color("Slider") == "#C3BD0E"
    assert scene3d.pt_color("X", 0) == "#1f77b4"


import numpy as np
import pandas as pd
from trajectory import scene3d as s3


def _rows():
    return pd.DataFrame({
        "TaggedPitchType": ["Fastball", "Slider"],
        "RelSpeed": [94.0, 84.0], "SpinRate": [2300, 2500],
        "RelSide": [-1.8, -1.7], "RelHeight": [5.9, 5.8], "Extension": [6.5, 6.4],
        "InducedVertBreak": [16.0, 2.0], "HorzBreak": [-8.0, 7.0],
        "PlateLocSide": [0.2, -0.3], "PlateLocHeight": [2.8, 2.1],
    })


def test_build_pitch_animation_ok_and_empty():
    fig, metas = s3.build_pitch_animation(_rows(), n_points=20, title="P")
    assert isinstance(fig, go.Figure) and len(fig.frames) == 20 and len(metas) == 2
    fig2, metas2 = s3.build_pitch_animation(pd.DataFrame({"TaggedPitchType": []}))
    assert fig2 is None and metas2 == []


def test_ribbon_and_ball_trace_counts():
    path = [(0, 54, 6, 0.0), (0.1, 30, 4, 0.2), (0.2, 1.42, 2.8, 0.4)]
    assert len(s3.pitch_ribbon_traces(path, "#D22D49", "FB")) == 3
    assert len(s3.ball_marker_traces(0, 1.42, 2.8, "#D22D49", label="K")) == 3
    assert len(s3.ball_marker_traces(0, 1.42, 2.8, "#D22D49")) == 2

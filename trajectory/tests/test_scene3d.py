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

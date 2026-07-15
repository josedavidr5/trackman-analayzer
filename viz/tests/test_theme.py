import plotly.graph_objects as go
from viz import theme
from core.metrics import ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP

def test_empty_fig_returns_figure():
    fig = theme.empty_fig("nada que mostrar")
    assert isinstance(fig, go.Figure)
    assert fig.layout.annotations[0].text == "nada que mostrar"
    assert fig.layout.xaxis.visible is False
    assert fig.layout.yaxis.visible is False

def test_color_map_maps_types():
    cm = theme.color_map(["Slider", "Fastball"])
    assert cm["Slider"] == "#C3BD0E"
    assert set(cm) == {"Slider", "Fastball"}

def test_strike_zone_shapes_has_rect():
    shapes = theme.strike_zone_shapes()
    assert shapes and shapes[0]["type"] == "rect"
    assert shapes[0]["x0"] == -ZONE_HALF_WIDTH
    assert shapes[0]["x1"] == ZONE_HALF_WIDTH
    assert shapes[0]["y0"] == ZONE_BOTTOM
    assert shapes[0]["y1"] == ZONE_TOP

def test_base_layout_has_white_bg():
    lay = theme.base_layout("Titulo", "sub")
    assert lay["paper_bgcolor"] == "#ffffff"
    assert "sub" in lay["title"]["text"]
    assert lay["plot_bgcolor"] == "#ffffff"

def test_home_plate_shape_is_line():
    s = theme.home_plate_shape()
    assert s["type"] == "line"

def test_movement_rings_four_circles():
    rings = theme.movement_rings()
    assert len(rings) == 4
    assert all(r["type"] == "circle" for r in rings)

import plotly.graph_objects as go
from viz import theme

def test_empty_fig_returns_figure():
    fig = theme.empty_fig("nada que mostrar")
    assert isinstance(fig, go.Figure)

def test_color_map_maps_types():
    cm = theme.color_map(["Slider", "Fastball"])
    assert cm["Slider"] == "#C3BD0E"
    assert set(cm) == {"Slider", "Fastball"}

def test_strike_zone_shapes_has_rect():
    shapes = theme.strike_zone_shapes()
    assert shapes and shapes[0]["type"] == "rect"

def test_base_layout_has_white_bg():
    lay = theme.base_layout("Titulo", "sub")
    assert lay["paper_bgcolor"] == "#ffffff"

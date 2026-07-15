import numpy as np
import plotly.graph_objects as go
from viz.export import plotly_png_array

def test_plotly_png_array_returns_array_or_none():
    fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))
    out = plotly_png_array(fig)
    # Con kaleido instalado → np.ndarray; sin kaleido → None (degradación).
    assert out is None or isinstance(out, np.ndarray)

def test_plotly_png_array_never_raises_on_bad_input():
    assert plotly_png_array(None) is None

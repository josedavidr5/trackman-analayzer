"""Tema Plotly en el lenguaje visual de Baseball Savant. Self-contained (CSP-safe)."""
import plotly.graph_objects as go
from core.metrics import pitch_color, ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP

BG = "#ffffff"
GRID = "#f0f0f0"
TEXT = "#333333"
GREY = "#7f7f7f"

def color_map(types):
    return {t: pitch_color(t, i) for i, t in enumerate(types)}

def strike_zone_shapes():
    return [dict(type="rect", x0=-ZONE_HALF_WIDTH, x1=ZONE_HALF_WIDTH,
                 y0=ZONE_BOTTOM, y1=ZONE_TOP, line=dict(color="#111111", width=2),
                 fillcolor="rgba(0,0,0,0)", layer="below")]

def home_plate_shape():
    return dict(type="line", x0=-0.71, x1=0.71, y0=0.25, y1=0.25,
                line=dict(color=GREY, width=3), layer="below")

def movement_rings():
    return [dict(type="circle", x0=-r, x1=r, y0=-r, y1=r,
                 line=dict(color="#e6e6e6", width=1), layer="below") for r in (6, 12, 18, 24)]

def base_layout(title, subtitle=""):
    txt = f"<b>{title}</b>"
    if subtitle:
        txt += f"<br><span style='font-size:12px;color:{GREY}'>{subtitle}</span>"
    return dict(
        title=dict(text=txt, x=0.01, xanchor="left"),
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=TEXT, size=12),
        margin=dict(l=55, r=20, t=64, b=48), hovermode="closest",
        legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#e5e5e5", borderwidth=1),
    )

def empty_fig(msg):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(color=GREY, size=14))
    lay = base_layout("")
    lay["xaxis"] = dict(visible=False)
    lay["yaxis"] = dict(visible=False)
    fig.update_layout(**lay)
    return fig

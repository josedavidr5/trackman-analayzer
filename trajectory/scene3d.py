"""trajectory.scene3d — constructores Plotly puros del look 'Statcast 3D'.
Sin Streamlit. Escena diurna (catcher view), cintas glossy y pelotas con halo."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .engine import compute_pitch_path, pitch_metrics, PLATE_Y

STATCAST_COLORS = {
    "4-Seam": "#D22D49", "Fastball": "#D22D49", "Four-Seam Fastball": "#D22D49",
    "2-Seam": "#DE6A04", "Sinker": "#FE9D00", "Cutter": "#933F2C", "Slider": "#C3BD0E",
    "Sweeper": "#DDB33A", "Curve": "#00D1ED", "Curveball": "#00D1ED",
    "Change": "#1DBE3A", "Changeup": "#1DBE3A", "Split": "#3BACAC",
    "Knuckleball": "#3C44CD", "Screwball": "#60DB33",
}
_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2"]


def pt_color(pt, idx=0):
    return STATCAST_COLORS.get(str(pt), _PALETTE[idx % len(_PALETTE)])


ZONE_X, ZONE_LO, ZONE_HI = 0.83, 1.5, 3.5
GRASS, DIRT = "#4a7c3f", "#b06a43"
SKY_LO, SKY_HI, BG = "#f3d9c0", "#9cc3e0", "#bcd7ea"


def _rgb(h):
    h = h.lstrip("#")
    return f"rgb({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)})"


def _lighten(hexc, f=0.55):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgb({int(r+(255-r)*f)},{int(g+(255-g)*f)},{int(b+(255-b)*f)})"


def field_scene_traces():
    """Escena diurna híbrida: cielo degradado, césped, tierra, zona 3×3, plato, foul, goma."""
    t = []
    # cielo: quad vertical lejano con degradado vertexcolor (horizonte→cenit)
    t.append(go.Mesh3d(
        x=[-42, 42, 42, -42], y=[71, 71, 71, 71], z=[0, 0, 17, 17],
        i=[0, 0], j=[1, 2], k=[2, 3],
        vertexcolor=[_rgb(SKY_LO), _rgb(SKY_LO), _rgb(SKY_HI), _rgb(SKY_HI)],
        hoverinfo="skip", showscale=False, lighting=dict(ambient=1.0, diffuse=0.0)))
    # césped
    t.append(go.Mesh3d(
        x=[-35, 35, 35, -35], y=[-2, -2, 70, 70], z=[0, 0, 0, 0], i=[0, 0], j=[1, 2], k=[2, 3],
        color=GRASS, hoverinfo="skip", showscale=False,
        lighting=dict(ambient=0.78, diffuse=0.5, specular=0.12),
        lightposition=dict(x=0, y=-30, z=60)))
    # tierra del home + montículo
    t.append(go.Mesh3d(x=[-8, 8, 8, -8], y=[-2, -2, 9, 9], z=[0.01] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3], color=DIRT, hoverinfo="skip", showscale=False))
    t.append(go.Mesh3d(x=[-6, 6, 6, -6], y=[54, 54, 64, 64], z=[0.01] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3], color=DIRT, opacity=0.92, hoverinfo="skip", showscale=False))
    # zona 3×3: panel + marco + grid
    y = PLATE_Y
    t.append(go.Mesh3d(x=[-ZONE_X, ZONE_X, ZONE_X, -ZONE_X], y=[y] * 4,
        z=[ZONE_LO, ZONE_LO, ZONE_HI, ZONE_HI], i=[0, 0], j=[1, 2], k=[2, 3],
        color="#ffffff", opacity=0.12, hoverinfo="skip", showscale=False))
    t.append(go.Scatter3d(x=[-ZONE_X, ZONE_X, ZONE_X, -ZONE_X, -ZONE_X], y=[y] * 5,
        z=[ZONE_LO, ZONE_LO, ZONE_HI, ZONE_HI, ZONE_LO], mode="lines",
        line=dict(color="#ffffff", width=6), opacity=0.95, showlegend=False, hoverinfo="skip"))
    for f in (1 / 3, 2 / 3):
        gx = -ZONE_X + 2 * ZONE_X * f
        gz = ZONE_LO + (ZONE_HI - ZONE_LO) * f
        t.append(go.Scatter3d(x=[gx, gx], y=[y, y], z=[ZONE_LO, ZONE_HI], mode="lines",
            line=dict(color="#ffffff", width=2), opacity=0.35, showlegend=False, hoverinfo="skip"))
        t.append(go.Scatter3d(x=[-ZONE_X, ZONE_X], y=[y, y], z=[gz, gz], mode="lines",
            line=dict(color="#ffffff", width=2), opacity=0.35, showlegend=False, hoverinfo="skip"))
    # plato, foul, goma
    t.append(go.Scatter3d(x=[-0.71, 0.71, 0.71, 0, -0.71, -0.71], y=[y, y, 0.4, 0.1, 0.4, y],
        z=[0.02] * 6, mode="lines", line=dict(color="#ffffff", width=5), opacity=0.95,
        showlegend=False, hoverinfo="skip"))
    for sgn in (1, -1):
        t.append(go.Scatter3d(x=[sgn * 0.71, sgn * 20.0], y=[1.4, 22.0], z=[0.02, 0.02],
            mode="lines", line=dict(color="#ffffff", width=3), opacity=0.5,
            showlegend=False, hoverinfo="skip"))
    t.append(go.Scatter3d(x=[-0.9, 0.9], y=[60.5, 60.5], z=[0.83, 0.83], mode="lines",
        line=dict(color="#f2f2f2", width=6), opacity=0.8, showlegend=False, hoverinfo="skip"))
    return t


def catcher_scene_layout(title=""):
    """Layout compartido con cámara catcher (detrás del plato → pitcher) y aspecto calibrado."""
    ax = dict(visible=False, showgrid=False, zeroline=False,
              showbackground=False, showticklabels=False)
    return dict(
        title=dict(text=title, font=dict(color="#12324a", size=15), x=0.03),
        height=640, margin=dict(l=0, r=0, t=44, b=0), paper_bgcolor=BG, showlegend=False,
        scene=dict(
            bgcolor=BG,
            xaxis={**ax, "range": [-6, 6]},
            yaxis={**ax, "range": [66, -2.5]},   # reversed: release atrás, plato adelante
            zaxis={**ax, "range": [-0.1, 11]},
            aspectmode="manual", aspectratio=dict(x=1, y=2.2, z=0.9),
            camera=dict(eye=dict(x=0.0, y=-1.95, z=0.42),
                        center=dict(x=0, y=-0.20, z=-0.05),
                        up=dict(x=0, y=0, z=1))))

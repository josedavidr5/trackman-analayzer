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
    # cielo: quad vertical lejano con degradado vertexcolor (horizonte→cenit), ancho para
    # que llene el fondo detrás del campo
    lo, hi = _rgb(SKY_LO), _rgb(SKY_HI)
    t.append(go.Mesh3d(
        x=[-75, 75, 75, -75], y=[58.4, 58.4, 58.4, 58.4], z=[0, 0, 17, 17],
        i=[0, 0], j=[1, 2], k=[2, 3],
        vertexcolor=[lo, lo, hi, hi],
        hoverinfo="skip", showscale=False, lighting=dict(ambient=1.0, diffuse=0.0)))
    # césped (ancho de borde a borde para que no flote)
    t.append(go.Mesh3d(
        x=[-62, 62, 62, -62], y=[-3, -3, 58, 58], z=[0, 0, 0, 0], i=[0, 0], j=[1, 2], k=[2, 3],
        color=GRASS, hoverinfo="skip", showscale=False,
        lighting=dict(ambient=0.8, diffuse=0.45, specular=0.1),
        lightposition=dict(x=0, y=-30, z=60)))
    # tierra del home (círculo/área del plato) + montículo
    t.append(go.Mesh3d(x=[-11, 11, 11, -11], y=[-3, -3, 12, 12], z=[0.01] * 4,
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
    """Layout compartido con cámara catcher (detrás del plato → pitcher) y aspecto calibrado.

    Eje-y natural: plato (y≈1.4) cerca, pitcher (y≈60) lejos. La cámara se coloca DETRÁS
    del plato (y negativo) y baja (nivel de ojos del cátcher), mirando hacia el pitcher (+y).
    """
    ax = dict(visible=False, showgrid=False, zeroline=False,
              showbackground=False, showticklabels=False)
    return dict(
        title=dict(text=title, font=dict(color="#12324a", size=15), x=0.03),
        height=660, margin=dict(l=0, r=0, t=44, b=0), paper_bgcolor=BG, showlegend=False,
        scene=dict(
            bgcolor=BG,
            xaxis={**ax, "range": [-6, 6]},
            yaxis={**ax, "range": [-3, 56]},      # natural: plato cerca, pitcher lejos
            zaxis={**ax, "range": [0, 11]},
            aspectmode="manual", aspectratio=dict(x=1.0, y=2.0, z=0.6),
            camera=dict(eye=dict(x=0.0, y=-1.62, z=0.20),   # detrás y algo arriba del plato
                        center=dict(x=0.0, y=0.42, z=0.02),  # mira hacia el pitcher, zona centrada
                        up=dict(x=0, y=0, z=1),
                        projection=dict(type="perspective"))))


def pitch_ribbon_traces(path, color, label=""):
    """Cinta glossy por capas (glow + cuerpo + núcleo brillante) sobre los puntos reales."""
    xs = [p[0] for p in path]; ys = [p[1] for p in path]; zs = [p[2] for p in path]
    body = go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=color, width=12),
                        opacity=0.98, name=label)
    if label:
        body.update(hovertemplate=label + "<extra></extra>")
    else:
        body.update(hoverinfo="skip", showlegend=False)
    return [
        go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=color, width=24),
                     opacity=0.16, showlegend=False, hoverinfo="skip"),
        body,
        go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=_lighten(color), width=4),
                     opacity=0.9, showlegend=False, hoverinfo="skip"),
    ]


def ball_marker_traces(x, y, z, color, label="", core="#ffffff", opacity=1.0):
    """Pelota blanca con halo de color (anillo semitransparente + núcleo). Etiqueta opcional."""
    halo = go.Scatter3d(x=[x], y=[y], z=[z], mode="markers",
                        marker=dict(size=17, color=color, opacity=0.45 * opacity),
                        showlegend=False, hoverinfo="skip")
    corem = go.Scatter3d(x=[x], y=[y], z=[z], mode="markers",
                         marker=dict(size=9, color=core, opacity=opacity,
                                     line=dict(color=color, width=2)), showlegend=False)
    if label:
        corem.update(hovertemplate=label + "<extra></extra>")
    else:
        corem.update(hoverinfo="skip")
    out = [halo, corem]
    if label:
        out.append(go.Scatter3d(x=[x], y=[y], z=[z + 0.5], mode="text", text=[label],
                                textfont=dict(color="#12324a", size=11),
                                showlegend=False, hoverinfo="skip"))
    return out


def _pitch_label(row):
    import pandas as pd
    v = row.get("RelSpeed"); s = row.get("SpinRate")
    bits = [str(row.get("TaggedPitchType", "?"))]
    if pd.notna(v): bits.append(f"{float(v):.1f} mph")
    if pd.notna(s): bits.append(f"{float(s):.0f} rpm")
    return " · ".join(bits)


def build_pitch_animation(rows, n_points=50, title=""):
    """Animación 3D restyled (catcher view): cintas glossy + pelota con halo por el path real."""
    paths, labels, colors, metas = [], [], [], []
    for i, (_, r) in enumerate(rows.iterrows()):
        try:
            paths.append(compute_pitch_path(r, n_points=n_points))
        except ValueError:
            continue
        labels.append(_pitch_label(r)); colors.append(pt_color(r.get("TaggedPitchType"), i))
        metas.append(pitch_metrics(r))
    if not paths:
        return None, []
    base = list(field_scene_traces())
    for path, lab, col in zip(paths, labels, colors):
        base += pitch_ribbon_traces(path, col, lab)
        base += ball_marker_traces(path[0][0], path[0][1], path[0][2], col, core="#ffffff")
        base += ball_marker_traces(path[-1][0], path[-1][1], path[-1][2], col, label="")
    # traces animados (invisibles al inicio): estela + halo + núcleo por pitcheo
    anim_start = len(base)
    for path, col in zip(paths, colors):
        p0 = path[0]
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="lines",
            line=dict(color="#ffffff", width=4), opacity=0.0, showlegend=False, hoverinfo="skip"))
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="markers",
            marker=dict(size=15, color=col, opacity=0.0), showlegend=False, hoverinfo="skip"))
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="markers",
            marker=dict(size=9, color="#ffffff", opacity=0.0), showlegend=False, hoverinfo="skip"))
    frames = []
    for k in range(n_points):
        data = []
        for path, col in zip(paths, colors):
            seg = path[:k + 1]
            xs = [p[0] for p in seg]; ys = [p[1] for p in seg]; zs = [p[2] for p in seg]
            data.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                line=dict(color="#ffffff", width=3), opacity=0.6))
            data.append(go.Scatter3d(x=[xs[-1]], y=[ys[-1]], z=[zs[-1]], mode="markers",
                marker=dict(size=15, color=col, opacity=0.5)))
            data.append(go.Scatter3d(x=[xs[-1]], y=[ys[-1]], z=[zs[-1]], mode="markers",
                marker=dict(size=9, color="#ffffff", opacity=1.0)))
        frames.append(go.Frame(data=data,
            traces=list(range(anim_start, anim_start + 3 * len(paths))), name=str(k)))
    fig = go.Figure(data=base, frames=frames)
    steps = [dict(method="animate", label=f"{k}",
                  args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}])
             for k in range(n_points)]
    fig.update_layout(**catcher_scene_layout(title))
    fig.update_layout(
        updatemenus=[dict(type="buttons", showactive=False, y=0.02, x=0.02, xanchor="left",
            bgcolor="rgba(255,255,255,0.25)", font=dict(color="#12324a"),
            bordercolor="rgba(0,0,0,0.2)", buttons=[
                dict(label="▶ Play", method="animate",
                     args=[None, {"frame": {"duration": 28, "redraw": True},
                                  "fromcurrent": True, "transition": {"duration": 0}}]),
                dict(label="⏸", method="animate",
                     args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]),
            ])],
        sliders=[dict(steps=steps, active=0, y=0.0, x=0.18, len=0.78,
                      currentvalue=dict(prefix="frame ", font=dict(color="#12324a")),
                      font=dict(color="#12324a"), bgcolor="rgba(255,255,255,0.4)",
                      bordercolor="rgba(0,0,0,0)")])
    return fig, metas


_TERMINAL = {"1B", "2B", "3B", "HR", "Out", "K", "BB", "HBP", "FC", "Error", "SacFly", "SacBunt"}


def pitches_thrown_figure(rows, title=""):
    """Vista 3D de pelotas ubicadas en la zona, anillo de color por tipo, etiqueta de resultado."""
    import pandas as pd
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(rows.columns):
        fig = go.Figure(data=field_scene_traces())
        fig.update_layout(**catcher_scene_layout(title or "Pitches Thrown"))
        fig.add_annotation(text="Sin datos de ubicación", showarrow=False,
                           font=dict(color="#12324a", size=14))
        return fig
    loc = rows.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    data = list(field_scene_traces())
    for i, (_, r) in enumerate(loc.iterrows()):
        col = pt_color(r.get("TaggedPitchType"), i)
        res = str(r.get("PlayResult", "")) if pd.notna(r.get("PlayResult", np.nan)) else ""
        label = res if res in _TERMINAL else ""
        data += ball_marker_traces(float(r["PlateLocSide"]), PLATE_Y, float(r["PlateLocHeight"]),
                                   col, label=label)
    fig = go.Figure(data=data)
    fig.update_layout(**catcher_scene_layout(title or "Pitches Thrown"))
    # sin trayectorias hacia el release: recortar el campo lejano y centrar la cámara en la zona
    fig.update_scenes(yaxis_range=[-3, 20], aspectratio=dict(x=1.0, y=1.05, z=0.72),
                      camera=dict(eye=dict(x=0.0, y=-1.7, z=0.42),
                                  center=dict(x=0.0, y=-0.05, z=-0.02),
                                  up=dict(x=0, y=0, z=1),
                                  projection=dict(type="perspective")))
    return fig

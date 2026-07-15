"""Constructores de figuras Plotly para el modo Pitching. DataFrame/dict → go.Figure."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from viz import theme


def _f(v, dec=1):
    return "—" if v is None else f"{v:.{dec}f}"


def movement_bubble(points, name, show_individual=True):
    cents = points.get("centroids", [])
    if not cents:
        return theme.empty_fig("No movement data")
    types = [c["pitch_type"] for c in cents]
    cmap = theme.color_map(types)
    fig = go.Figure()
    if show_individual:
        for c in cents:
            pts = [p for p in points["pitches"] if p["pitch_type"] == c["pitch_type"]]
            if pts:
                fig.add_trace(go.Scatter(
                    x=[p["hb"] for p in pts], y=[p["ivb"] for p in pts], mode="markers",
                    marker=dict(size=5, color=cmap[c["pitch_type"]], opacity=0.35,
                                line=dict(width=0.4, color="white")),
                    name=c["pitch_type"], legendgroup=c["pitch_type"],
                    showlegend=False, hoverinfo="skip"))
    umax = max((max(c["usage"], 0.0) for c in cents), default=1.0) or 1.0
    for c in cents:
        size = 18 + 42 * (max(c["usage"], 0.0) / umax)
        hover = (f"<b>{c['pitch_type']}</b> (n={c['n']})<br>"
                 f"Usage: {c['usage']:.1f}%<br>"
                 f"Velo: {_f(c['avg_velo'])} (max {_f(c['max_velo'])})<br>"
                 f"Spin: {_f(c['avg_spin'], 0)}<br>"
                 f"IVB: {c['ivb']:.1f}\"  HB: {c['hb']:.1f}\"<br>"
                 f"Whiff: {_f(c['whiff'])}%  CSW: {_f(c['csw'])}%<extra></extra>")
        fig.add_trace(go.Scatter(
            x=[c["hb"]], y=[c["ivb"]], mode="markers+text",
            marker=dict(size=size, color=cmap[c["pitch_type"]], opacity=0.95,
                        line=dict(width=2, color="white")),
            text=[c["pitch_type"]], textposition="top center",
            textfont=dict(size=10, color="#222222"),
            name=c["pitch_type"], legendgroup=c["pitch_type"], hovertemplate=hover))
    lim = 27
    lay = theme.base_layout("Pitch Movement", f"{name} · vista del catcher")
    lay["shapes"] = theme.movement_rings()
    lay["xaxis"] = dict(range=[-lim, lim], zeroline=True, zerolinecolor="#d2d2d2",
                        gridcolor=theme.GRID, title="Horizontal Break (in) · arm side →")
    lay["yaxis"] = dict(range=[-lim, lim], zeroline=True, zerolinecolor="#d2d2d2",
                        gridcolor=theme.GRID, scaleanchor="x", scaleratio=1,
                        title="Induced Vertical Break (in) · ride →")
    fig.update_layout(**lay)
    return fig

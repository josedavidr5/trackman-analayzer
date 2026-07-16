"""Constructores de figuras Plotly para el modo Hitting. DataFrame/dict → go.Figure."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from viz import theme

RESULT_COLORS = {"1B": "#1DBE3A", "2B": "#00D1ED", "3B": "#9467bd", "HR": "#D22D49", "Out": "#8899a6"}


def _h(v):
    return "—" if v is None else f"{v:.1f}"


def ev_distribution(df, name):
    if "ExitSpeed" not in df.columns or df["ExitSpeed"].dropna().empty:
        return theme.empty_fig("No EV data")
    ev = df["ExitSpeed"].dropna()
    fig = go.Figure(go.Histogram(x=ev, nbinsx=24, marker_color=theme.GREY, opacity=0.85))
    fig.add_vline(x=95, line=dict(color="#D22D49", width=1.4, dash="dot"))
    fig.add_vline(x=float(ev.mean()), line=dict(color=theme.TEXT, width=1.6, dash="dash"))
    lay = theme.base_layout("Exit Velocity Distribution",
                            f"{name} · HH {int((ev >= 95).sum())} ({round(100 * (ev >= 95).mean(), 1)}%)")
    lay["xaxis"] = dict(title="Exit Velocity (mph)", gridcolor=theme.GRID)
    lay["yaxis"] = dict(title="Count", gridcolor=theme.GRID)
    fig.update_layout(**lay)
    return fig


def la_distribution(df, name):
    if "Angle" not in df.columns or df["Angle"].dropna().empty:
        return theme.empty_fig("No LA data")
    la = df["Angle"].dropna()
    fig = go.Figure(go.Histogram(x=la, nbinsx=24, marker_color=theme.GREY, opacity=0.85))
    fig.add_vrect(x0=8, x1=32, fillcolor="#1DBE3A", opacity=0.10, line_width=0)
    fig.add_vline(x=float(la.mean()), line=dict(color=theme.TEXT, width=1.6, dash="dash"))
    barrel = int(((la >= 8) & (la <= 32)).sum())
    lay = theme.base_layout("Launch Angle Distribution",
                            f"{name} · sweet-spot {barrel} ({round(100 * barrel / len(la), 1)}%)")
    lay["xaxis"] = dict(title="Launch Angle (°)", gridcolor=theme.GRID)
    lay["yaxis"] = dict(title="Count", gridcolor=theme.GRID)
    fig.update_layout(**lay)
    return fig


def ev_la_scatter(df, name):
    if not {"ExitSpeed", "Angle"}.issubset(df.columns):
        return theme.empty_fig("No EV/LA data")
    sub = df.dropna(subset=["ExitSpeed", "Angle"])
    if sub.empty:
        return theme.empty_fig("No EV/LA data")
    fig = go.Figure()
    if "PlayResult" in sub.columns:
        for res, color in RESULT_COLORS.items():
            g = sub[sub["PlayResult"] == res]
            if len(g):
                fig.add_trace(go.Scatter(x=g["ExitSpeed"], y=g["Angle"], mode="markers", name=res,
                    marker=dict(size=8, color=color, opacity=0.8, line=dict(width=0.5, color="white")),
                    hovertemplate=f"{res}<br>%{{x:.1f}} mph · %{{y:.0f}}°<extra></extra>"))
        other = sub[~sub["PlayResult"].isin(RESULT_COLORS)]
        if len(other):
            fig.add_trace(go.Scatter(x=other["ExitSpeed"], y=other["Angle"], mode="markers",
                name="otros", marker=dict(size=5, color="#cccccc", opacity=0.4), hoverinfo="skip"))
    else:
        fig.add_trace(go.Scatter(x=sub["ExitSpeed"], y=sub["Angle"], mode="markers",
            marker=dict(size=7, color=theme.GREY, opacity=0.6)))
    fig.add_shape(type="rect", x0=98, x1=118, y0=8, y1=32,
                  line=dict(color="#1f77b4", width=1.5, dash="dash"),
                  fillcolor="rgba(31,119,180,0.06)", layer="below")
    lay = theme.base_layout("Hit Quality Map — EV × LA", name)
    lay["xaxis"] = dict(title="Exit Velocity (mph)", gridcolor=theme.GRID)
    lay["yaxis"] = dict(title="Launch Angle (°)", gridcolor=theme.GRID)
    fig.update_layout(**lay)
    return fig


def damage_zone(df, name):
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns):
        return theme.empty_fig("No location data")
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        return theme.empty_fig("No location data")
    has_ev = "ExitSpeed" in loc.columns and loc["ExitSpeed"].notna().any()
    marker = dict(size=11, line=dict(width=0.6, color="white"))
    if has_ev:
        marker.update(color=loc["ExitSpeed"], colorscale="RdBu_r", cmin=65, cmax=112,
                      showscale=True, colorbar=dict(title="EV"))
        hov = "EV %{marker.color:.1f}<br>side %{x:.2f} · height %{y:.2f}<extra></extra>"
    else:
        marker.update(color=theme.GREY)
        hov = "side %{x:.2f} · height %{y:.2f}<extra></extra>"
    fig = go.Figure(go.Scatter(x=loc["PlateLocSide"], y=loc["PlateLocHeight"], mode="markers",
                               marker=marker, hovertemplate=hov))
    lay = theme.base_layout("Damage Zone", f"{name} · dónde le pegan más duro")
    lay["shapes"] = theme.strike_zone_shapes()
    lay["xaxis"] = dict(range=[-2.0, 2.0], gridcolor=theme.GRID, zeroline=False)
    lay["yaxis"] = dict(range=[0.4, 4.6], gridcolor=theme.GRID, zeroline=False,
                        scaleanchor="x", scaleratio=1)
    fig.update_layout(**lay)
    return fig


def rolling_ev(df, name, window=15):
    from core.metrics import batted_ball_mask
    if "ExitSpeed" not in df.columns:
        return theme.empty_fig("No EV data")
    bip = df[batted_ball_mask(df)].dropna(subset=["ExitSpeed"]).copy()
    if "Date" in bip.columns:
        bip = bip.sort_values("Date")
    if len(bip) < 5:
        return theme.empty_fig("Need ≥ 5 batted balls")
    ev = bip["ExitSpeed"].reset_index(drop=True)
    roll = ev.rolling(window, min_periods=max(3, window // 3)).mean()
    x = np.arange(1, len(ev) + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=ev, mode="markers", name="Batted ball EV",
        marker=dict(size=6, color=theme.GREY, opacity=0.4)))
    fig.add_trace(go.Scatter(x=x, y=roll, mode="lines", name=f"Rolling ({window})",
        line=dict(color="#D22D49", width=2.4)))
    fig.add_hline(y=float(ev.mean()), line=dict(color=theme.GREY, width=1, dash="dash"))
    lay = theme.base_layout("Rolling Exit Velocity", name)
    lay["xaxis"] = dict(title="Batted ball # (cronológico)", gridcolor=theme.GRID)
    lay["yaxis"] = dict(title="Exit Velocity (mph)", gridcolor=theme.GRID)
    fig.update_layout(**lay)
    return fig


def spray_interactive(points, name, color_by="ev"):
    """Spray Plotly interactivo: campo estilizado + scatter con hover. color_by ∈ {'ev','result'}."""
    pts = points.get("points", []) if points else []
    if not pts:
        return theme.empty_fig("No spray data")
    t = np.linspace(-45, 45, 120)
    r = 330 + 70 * np.cos(np.deg2rad(t * 2))
    fx = (r * np.sin(np.deg2rad(t))).tolist(); fy = (r * np.cos(np.deg2rad(t))).tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0] + fx + [0], y=[0] + fy + [0], fill="toself",
        fillcolor="#e7f2e6", line=dict(color="#8bbf86", width=1), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=fx, y=fy, mode="lines", line=dict(color="#4a7c46", width=3),
        hoverinfo="skip", showlegend=False))
    for sgn in (1, -1):
        fig.add_trace(go.Scatter(x=[0, sgn * 330 * np.sin(np.deg2rad(45))],
            y=[0, 330 * np.cos(np.deg2rad(45))], mode="lines",
            line=dict(color="#b9c6b7", width=1.5), hoverinfo="skip", showlegend=False))
    xs = [p["x"] for p in pts]; ys = [p["y"] for p in pts]
    hov = [f"{p['result']}<br>EV {_h(p['ev'])} · LA {_h(p['la'])}° · {p['distance']:.0f} ft" for p in pts]
    if color_by == "result":
        for res, col in RESULT_COLORS.items():
            idx = [i for i, p in enumerate(pts) if p["result"] == res]
            if idx:
                fig.add_trace(go.Scatter(x=[xs[i] for i in idx], y=[ys[i] for i in idx], mode="markers",
                    name=res, marker=dict(size=10, color=col, line=dict(width=0.6, color="white")),
                    text=[hov[i] for i in idx], hovertemplate="%{text}<extra></extra>"))
    else:
        evs = [p["ev"] for p in pts]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", text=hov,
            marker=dict(size=10, color=evs, colorscale="RdBu_r", cmin=65, cmax=112, showscale=True,
                        colorbar=dict(title="EV"), line=dict(width=0.6, color="white")),
            hovertemplate="%{text}<extra></extra>", showlegend=False))
    lay = theme.base_layout("Spray Chart", name)
    lay["xaxis"] = dict(range=[-360, 360], visible=False)
    lay["yaxis"] = dict(range=[-40, 440], visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(**lay)
    return fig

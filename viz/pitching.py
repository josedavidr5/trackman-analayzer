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


def location_scatter(df, name):
    if not {"PlateLocSide", "PlateLocHeight", "TaggedPitchType"}.issubset(df.columns):
        return theme.empty_fig("No location data")
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        return theme.empty_fig("No location data")
    types = list(loc["TaggedPitchType"].dropna().unique())
    if not types:
        return theme.empty_fig("No location data")
    cmap = theme.color_map(types)
    fig = go.Figure()
    for pt, g in loc.groupby("TaggedPitchType"):
        velo = (g["RelSpeed"] if "RelSpeed" in g.columns
                else pd.Series([np.nan] * len(g), index=g.index))
        fig.add_trace(go.Scatter(
            x=g["PlateLocSide"], y=g["PlateLocHeight"], mode="markers", name=str(pt),
            marker=dict(size=8, color=cmap.get(pt, theme.GREY), opacity=0.75,
                        line=dict(width=0.5, color="white")),
            customdata=np.stack([velo.values], axis=-1),
            hovertemplate=(f"<b>{pt}</b><br>Velo: %{{customdata[0]:.1f}} mph<br>"
                           "side %{x:.2f} ft · height %{y:.2f} ft<extra></extra>")))
    lay = theme.base_layout("Pitch Locations", f"{name} · vista del catcher")
    lay["shapes"] = theme.strike_zone_shapes()
    lay["xaxis"] = dict(range=[-2.0, 2.0], gridcolor=theme.GRID, zeroline=False)
    lay["yaxis"] = dict(range=[0.4, 4.6], gridcolor=theme.GRID, zeroline=False,
                        scaleanchor="x", scaleratio=1)
    fig.update_layout(**lay)
    return fig


def hot_zone(df, name):
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns):
        return theme.empty_fig("No location data")
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if len(loc) < 5:
        return theme.empty_fig("Se requieren ≥ 5 pitches")
    fig = go.Figure(go.Histogram2dContour(
        x=loc["PlateLocSide"], y=loc["PlateLocHeight"],
        colorscale=[[0, "#ffffff"], [0.5, "#f6b6a8"], [1, "#D22D49"]],
        contours=dict(coloring="fill"), line=dict(width=0),
        hovertemplate="side %{x:.2f} · height %{y:.2f}<br>densidad %{z}<extra></extra>"))
    lay = theme.base_layout("Ubicación — Frecuencia", f"{name} · {len(loc)} pitches")
    lay["shapes"] = theme.strike_zone_shapes()
    lay["xaxis"] = dict(range=[-2.0, 2.0], gridcolor=theme.GRID, zeroline=False)
    lay["yaxis"] = dict(range=[0.4, 4.6], gridcolor=theme.GRID, zeroline=False,
                        scaleanchor="x", scaleratio=1)
    fig.update_layout(**lay)
    return fig


def location_by_pitch(df, name, max_types=6):
    if not {"PlateLocSide", "PlateLocHeight", "TaggedPitchType"}.issubset(df.columns):
        return theme.empty_fig("No location data")
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    types = (loc["TaggedPitchType"].value_counts().head(max_types).index.tolist()
             if not loc.empty else [])
    if not types:
        return theme.empty_fig("No location data")
    cmap = theme.color_map(types)
    ncols = min(len(types), 3)
    nrows = int(np.ceil(len(types) / ncols))
    titles = [f"{t} · n={int((loc['TaggedPitchType'] == t).sum())}" for t in types]
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=titles,
                        horizontal_spacing=0.06, vertical_spacing=0.12)
    for i, pt in enumerate(types):
        r, c = i // ncols + 1, i % ncols + 1
        g = loc[loc["TaggedPitchType"] == pt]
        fig.add_trace(go.Scatter(
            x=g["PlateLocSide"], y=g["PlateLocHeight"], mode="markers", showlegend=False,
            marker=dict(size=6, color=cmap[pt], opacity=0.7, line=dict(width=0.4, color="white")),
            hovertemplate=f"{pt}<br>%{{x:.2f}}, %{{y:.2f}}<extra></extra>"), row=r, col=c)
        fig.add_shape(theme.strike_zone_shapes()[0], row=r, col=c)
        fig.update_xaxes(range=[-2.0, 2.0], gridcolor=theme.GRID, zeroline=False, row=r, col=c)
        fig.update_yaxes(range=[0.4, 4.6], gridcolor=theme.GRID, zeroline=False, row=r, col=c)
    fig.update_layout(paper_bgcolor=theme.BG, plot_bgcolor=theme.BG,
                      font=dict(color=theme.TEXT, size=11),
                      title=dict(text=f"<b>Ubicación por tipo — {name}</b>", x=0.01),
                      margin=dict(l=40, r=20, t=72, b=40), height=300 * nrows)
    return fig


def velo_trend(df, name):
    if not {"RelSpeed", "Date", "TaggedPitchType"}.issubset(df.columns):
        return theme.empty_fig("No velocity data")
    vel = df.dropna(subset=["RelSpeed", "Date"])
    if vel.empty:
        return theme.empty_fig("No velocity data")
    types = list(vel["TaggedPitchType"].dropna().unique())
    cmap = theme.color_map(types)
    fig = go.Figure()
    for pt, g in vel.groupby("TaggedPitchType"):
        daily = g.sort_values("Date").groupby("Date")["RelSpeed"].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily["RelSpeed"], mode="lines+markers", name=str(pt),
            line=dict(color=cmap.get(pt, theme.GREY), width=2),
            marker=dict(size=6, line=dict(width=0.6, color="white")),
            hovertemplate=f"<b>{pt}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:.1f}} mph<extra></extra>"))
    lay = theme.base_layout("Velocity Tendency", name)
    lay["xaxis"] = dict(title="Date", gridcolor=theme.GRID)
    lay["yaxis"] = dict(title="Avg Velocity (mph)", gridcolor=theme.GRID)
    fig.update_layout(**lay)
    return fig


def usage_heatmap(tab, name):
    if tab is None or tab.empty:
        return theme.empty_fig("Balls/Strikes columns required")
    z = tab.values
    zmax = max(float(z.max()), 1.0)
    fig = go.Figure(go.Heatmap(
        z=z, x=list(tab.columns), y=list(tab.index), colorscale="Blues", zmin=0, zmax=zmax,
        text=[[f"{v:.0f}" if v > 0 else "" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=10),
        colorbar=dict(title="Usage %"),
        hovertemplate="%{y} · count %{x}<br>%{z:.1f}%<extra></extra>"))
    lay = theme.base_layout("Pitch Usage % by Count", name)
    lay["xaxis"] = dict(title="Count (Balls-Strikes)")
    lay["yaxis"] = dict(autorange="reversed")
    fig.update_layout(**lay)
    return fig


def zone_rate_heatmap(grid, metric, name):
    """Heatmap 5×5 de Whiff% o CSW% por celda. Celdas no confiables en gris (solo n)."""
    cells = grid.get("cells", [])
    if not cells:
        return theme.empty_fig("No hay datos de ubicación/PitchCall")
    rate_key = "whiff_pct" if metric == "whiff" else "csw_pct"
    rel_key = "whiff_reliable" if metric == "whiff" else "csw_reliable"
    label = "Whiff%" if metric == "whiff" else "CSW%"
    x_edges, z_edges = grid["x_edges"], grid["z_edges"]
    xc = [(x_edges[i] + x_edges[i + 1]) / 2 for i in range(5)]
    zc = [(z_edges[i] + z_edges[i + 1]) / 2 for i in range(5)]
    z = [[None] * 5 for _ in range(5)]
    hovertext = [["" for _ in range(5)] for _ in range(5)]
    ann = []
    for c in cells:
        ix, iz, n = c["ix"], c["iz"], c["n_pitches"]
        if n == 0:
            continue
        if c[rel_key]:
            z[iz][ix] = c[rate_key]
            if metric == "whiff":
                num, den = c["whiffs"], c["n_swings"]
            else:
                num, den = c["called"] + c["whiffs"], n
            hovertext[iz][ix] = f"{label}: {c[rate_key]:.0f}%<br>{num}/{den} · n={n}"
            ann.append(dict(x=xc[ix], y=zc[iz], text=f"{c[rate_key]:.0f}%<br>({n})",
                            showarrow=False, font=dict(size=10, color="#222222")))
        else:
            hovertext[iz][ix] = f"muestra baja · n={n}"
            ann.append(dict(x=xc[ix], y=zc[iz], text=f"({n})",
                            showarrow=False, font=dict(size=9, color="#999999")))
    fig = go.Figure(go.Heatmap(
        x=xc, y=zc, z=z, colorscale=[[0, "#ffffff"], [0.5, "#f6b6a8"], [1, "#D22D49"]],
        zmin=0, zmax=100, xgap=2, ygap=2, hoverongaps=False,
        colorbar=dict(title=label), hovertext=hovertext, hoverinfo="text"))
    lay = theme.base_layout(f"{label} por zona", f"{name} · vista del catcher")
    lay["shapes"] = theme.strike_zone_shapes()
    lay["annotations"] = ann
    lay["xaxis"] = dict(range=[-1.5, 1.5], gridcolor=theme.GRID, zeroline=False)
    lay["yaxis"] = dict(range=[0.7, 4.3], gridcolor=theme.GRID, zeroline=False,
                        scaleanchor="x", scaleratio=1)
    fig.update_layout(**lay)
    return fig

# Hitting interactivo + Spray Broadcast — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. Task 5 (visual tuning del spray) requiere ver PNGs renderizados — es trabajo de controller/humano.

**Goal:** Llevar el modo Hitting al nivel de Pitching: extraer analítica a `core/hitting.py`, gráficos a `viz/hitting.py` (Plotly interactivo), y un **spray chart broadcast** (matplotlib foto-realista top-down + toggle interactivo Plotly).

**Architecture:** Patrón de iters 1-2. `core/hitting.py` (analítica pura), `viz/hitting.py` (Plotly), `viz/spray_render.py` (matplotlib foto-realista, como `viz/export.py`). `render_hitting` orquesta.

**Tech Stack:** Python, pandas, numpy, Streamlit, Plotly, matplotlib (spray foto-realista + PDF vía kaleido), pytest.

## Global Constraints

- `core/hitting.py` NO importa `streamlit` ni `matplotlib`. Solo `pandas`/`numpy` + `core.metrics`.
- `viz/hitting.py` NO importa `streamlit`; solo `plotly` (+numpy/pandas) y `core`/`viz.theme`.
- `viz/spray_render.py` usa `matplotlib` (excepción, como `viz/export.py`); NO importa `streamlit`.
- Funciones movidas: se **mueven** del monolito y se importan (con alias); sin duplicados.
- Spray: campo **top-down de día**; color con toggle **EV ↔ resultado**; panel de bateo al lado.
- Coordenadas spray: `x = Distance·sin(Bearing°)`, `y = Distance·cos(Bearing°)` (home en (0,0), y hacia CF).
- Tests desde la raíz con `.venv/bin/python -m pytest`. Rama: `iter4-hitting-broadcast`. Un commit por tarea.
- No mover `build_league_hitting_avg` (es de League, usa `fmt`).

---

### Task 1: `core/hitting.py` — analítica de bateo (mover + helpers nuevos)

**Files:**
- Create: `core/hitting.py`, `core/tests/test_hitting.py`
- Modify: `trackman_app.py` (borrar defs locales, importar de `core.hitting`)

**Interfaces:**
- Consumes: `core.metrics.{safe_pct, count_pa, count_k_bb, in_zone_mask, batted_ball_mask, barrel_mask, compute_woba, SWING_CALLS, CONTACT_CALLS}`
- Produces: `build_play_result_table(df)`, `compute_plate_discipline_batter(df)`,
  `build_split_table(df, split_col="PitcherThrows", ev_hard=95)`, `build_hitting_monthly(df, lmeta=None)`,
  `batted_balls(df) -> DataFrame`, `spray_points(df) -> dict`, `hitting_summary(df, lmeta=None) -> dict`.

- [ ] **Step 1: Escribir tests primero — `core/tests/test_hitting.py`**

```python
import numpy as np, pandas as pd
import pytest
from core.hitting import (spray_points, hitting_summary, build_split_table, build_play_result_table)

def _bb():
    return pd.DataFrame({
        "Batter": ["A"] * 5,
        "PitchCall": ["InPlay"] * 5,
        "PlayResult": ["1B", "HR", "Out", "2B", "Out"],
        "ExitSpeed": [98.0, 104.0, 80.0, 95.0, 88.0],
        "Angle": [12.0, 28.0, -5.0, 20.0, 45.0],
        "Distance": [150.0, 410.0, 60.0, 330.0, 120.0],
        "Bearing": [0.0, 10.0, -20.0, 25.0, -35.0],
        "PitcherThrows": ["R", "R", "L", "R", "L"],
    })

def test_spray_points_xy():
    pts = spray_points(_bb())["points"]
    assert len(pts) == 5
    # Bearing 0 → x=0, y=Distance
    p0 = pts[0]
    assert p0["x"] == pytest.approx(0.0, abs=1e-6)
    assert p0["y"] == pytest.approx(150.0)
    assert p0["result"] == "1B" and p0["ev"] == 98.0

def test_spray_points_missing_cols():
    assert spray_points(pd.DataFrame({"ExitSpeed": [90.0]}))["points"] == []

def test_hitting_summary_metrics():
    s = hitting_summary(_bb(), {"ev_hard": 95, "barrel_ev": 98})
    assert s["n"] == 5
    assert s["max_ev"] == 104.0
    assert s["avg_ev"] == pytest.approx(np.mean([98, 104, 80, 95, 88]))
    # HH% = EV>=95 → 98,104,95 = 3/5 = 60.0
    assert s["hh_pct"] == 60.0

def test_build_split_table_by_hand():
    t = build_split_table(_bb(), ev_hard=95)
    assert set(t["vs"]) == {"R", "L"}

def test_build_play_result_table():
    t = build_play_result_table(_bb())
    assert "Result" in t.columns and int(t["Count"].sum()) == 5
```

- [ ] **Step 2: Correr — deben fallar** (`ModuleNotFoundError: core.hitting`)

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/test_hitting.py -v`

- [ ] **Step 3: Crear `core/hitting.py`**

Copiar **verbatim** desde `trackman_app.py` las 4 funciones: `build_play_result_table`
(actual :773), `compute_plate_discipline_batter` (:782), `build_split_table` (:814),
`build_hitting_monthly` (:832). Añadir el import y los 3 helpers nuevos:

```python
"""Analítica de bateo pura — pandas/numpy. Sin Streamlit ni matplotlib."""
import numpy as np
import pandas as pd
from core.metrics import (safe_pct, count_pa, count_k_bb, in_zone_mask, batted_ball_mask,
                          barrel_mask, compute_woba, SWING_CALLS, CONTACT_CALLS)

# ── movidas verbatim del monolito ──
def build_play_result_table(df):
    if "PlayResult" not in df.columns: return pd.DataFrame()
    counts = df["PlayResult"].value_counts().reset_index()
    counts.columns = ["Result", "Count"]
    counts = counts[counts["Result"] != "—"]
    pa = max(count_pa(df), 1)
    counts["% of PAs"] = counts["Count"].apply(lambda x: safe_pct(x, pa))
    return counts.reset_index(drop=True)

def compute_plate_discipline_batter(df):
    """Disciplina del bateador: Zone/Chase reales, K%/BB% por PA."""
    if "PitchCall" not in df.columns: return {}
    pc = df["PitchCall"].astype(str)
    ZONE_CALLS = {"StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallFieldable",
                  "FoulBallNotFieldable", "InPlay"}
    n = len(df)
    sw_m = pc.isin(SWING_CALLS); ct_m = pc.isin(CONTACT_CALLS)
    sw, cont, whiff = int(sw_m.sum()), int(ct_m.sum()), int(pc.eq("StrikeSwinging").sum())
    zone_m, has_loc = in_zone_mask(df)
    if has_loc:
        located = df["PlateLocSide"].notna() & df["PlateLocHeight"].notna()
        in_z = int(zone_m.sum()); n_loc = int(located.sum())
        oz = located & ~zone_m
        zone_pct = safe_pct(in_z, n_loc)
        chase_pct = safe_pct(int((sw_m & oz).sum()), max(int(oz.sum()), 1))
    else:
        in_z = int(pc.isin(ZONE_CALLS).sum())
        zone_pct = safe_pct(in_z, n)
        chase_pct = safe_pct(max(0, sw - cont), max(n - in_z, 1))
    pa = count_pa(df); kk, bb = count_k_bb(df)
    return {"Zone %": zone_pct, "Swing %": safe_pct(sw, n),
            "Contact %": safe_pct(cont, max(sw, 1)), "Chase %": chase_pct,
            "Whiff %": safe_pct(whiff, max(sw, 1)),
            "K %": safe_pct(kk, max(pa, 1)), "BB %": safe_pct(bb, max(pa, 1))}

def build_split_table(df, split_col="PitcherThrows", ev_hard=95):
    if split_col not in df.columns: return pd.DataFrame()
    rows = []
    for hand, grp in df.groupby(split_col):
        n = len(grp); r = {"vs": hand, "Pitches": n, "PA": count_pa(grp)}
        if "ExitSpeed" in grp.columns:
            ev = grp["ExitSpeed"].dropna()
            r["Avg EV"] = round(ev.mean(), 1) if not ev.empty else np.nan
            r["HH %"] = safe_pct((ev >= ev_hard).sum(), len(ev))
        if "Angle" in grp.columns:
            la = grp["Angle"].dropna()
            r["Avg LA"] = round(la.mean(), 1) if not la.empty else np.nan
        r.update({k: v for k, v in compute_plate_discipline_batter(grp).items()})
        r["wOBA"] = compute_woba(grp)
        rows.append(r)
    return pd.DataFrame(rows).reset_index(drop=True)

def build_hitting_monthly(df, lmeta=None):
    ev_hard = (lmeta or {}).get("ev_hard", 95)
    barrel_base = (lmeta or {}).get("barrel_ev", 98)
    df = df.copy(); df["YearMonth"] = df["Date"].dt.to_period("M")
    rows = []
    for period, grp in df.groupby("YearMonth"):
        r = {"Month": str(period), "Pitches": len(grp), "PA": count_pa(grp)}
        for col, (mx, av) in [("ExitSpeed", ("Max EV", "Avg EV")), ("Angle", ("Max LA", "Avg LA")),
                              ("Distance", ("Max Dist", "Avg Dist"))]:
            if col in df.columns:
                vals = grp[col].dropna()
                r[mx] = round(vals.max(), 1) if not vals.empty else np.nan
                r[av] = round(vals.mean(), 1) if not vals.empty else np.nan
        bip = batted_ball_mask(grp); n_bip = int(bip.sum())
        if "ExitSpeed" in df.columns:
            ev = grp.loc[bip, "ExitSpeed"].dropna()
            r["HH %"] = safe_pct(int((ev >= ev_hard).sum()), max(len(ev), 1))
        if "ExitSpeed" in df.columns and "Angle" in df.columns:
            barrels = int(barrel_mask(grp[bip], barrel_base).sum()) if n_bip else 0
            r["Barrel %"] = safe_pct(barrels, max(n_bip, 1))
        kk, bb = count_k_bb(grp); pa = max(count_pa(grp), 1)
        r["K %"] = safe_pct(kk, pa); r["BB %"] = safe_pct(bb, pa)
        r["wOBA"] = compute_woba(grp)
        rows.append(r)
    out = pd.DataFrame(rows)
    return out.sort_values("Month", ascending=False).reset_index(drop=True) if not out.empty else out

# ── helpers nuevos ──
def batted_balls(df):
    """Filas con contacto (batted balls)."""
    m = batted_ball_mask(df)
    return df[m].copy() if bool(m.any()) else df.iloc[0:0].copy()

def spray_points(df):
    """Por batazo con Distance+Bearing: dict {'points': [{x,y,ev,la,distance,result}]}."""
    if not {"Distance", "Bearing"}.issubset(df.columns):
        return {"points": []}
    sub = df.dropna(subset=["Distance", "Bearing"])
    if sub.empty:
        return {"points": []}
    brad = np.deg2rad(sub["Bearing"].to_numpy(dtype=float))
    dist = sub["Distance"].to_numpy(dtype=float)
    xs = dist * np.sin(brad); ys = dist * np.cos(brad)
    ev = sub["ExitSpeed"].to_numpy() if "ExitSpeed" in sub.columns else np.full(len(sub), np.nan)
    la = sub["Angle"].to_numpy() if "Angle" in sub.columns else np.full(len(sub), np.nan)
    res = sub["PlayResult"].astype(str).to_numpy() if "PlayResult" in sub.columns else np.array([""] * len(sub))
    pts = []
    for i in range(len(sub)):
        pts.append({"x": float(xs[i]), "y": float(ys[i]),
                    "ev": float(ev[i]) if pd.notna(ev[i]) else None,
                    "la": float(la[i]) if pd.notna(la[i]) else None,
                    "distance": float(dist[i]), "result": str(res[i])})
    return {"points": pts}

def hitting_summary(df, lmeta=None):
    """Métricas de cabecera/panel: n, pa, avg/max EV, avg LA, HH%, Barrel%, wOBA."""
    ev_hard = (lmeta or {}).get("ev_hard", 95)
    barrel_base = (lmeta or {}).get("barrel_ev", 98)
    bip = batted_ball_mask(df); n_bip = int(bip.sum())
    def _f(v): return float(v) if v is not None and pd.notna(v) else None
    ev = df.loc[bip, "ExitSpeed"].dropna() if "ExitSpeed" in df.columns else pd.Series(dtype=float)
    la = df.loc[bip, "Angle"].dropna() if "Angle" in df.columns else pd.Series(dtype=float)
    hh = safe_pct(int((ev >= ev_hard).sum()), max(len(ev), 1)) if len(ev) else 0.0
    barrel = (safe_pct(int(barrel_mask(df[bip], barrel_base).sum()), n_bip)
              if n_bip and {"ExitSpeed", "Angle"}.issubset(df.columns) else 0.0)
    return {"n": int(len(df)), "pa": int(count_pa(df)),
            "avg_ev": _f(ev.mean()) if len(ev) else None,
            "max_ev": _f(ev.max()) if len(ev) else None,
            "avg_la": _f(la.mean()) if len(la) else None,
            "hh_pct": hh, "barrel_pct": barrel, "woba": _f(compute_woba(df))}
```

- [ ] **Step 4: Correr los tests — deben pasar** (`.venv/bin/python -m pytest core/tests/test_hitting.py -v` → 5 passed)

- [ ] **Step 5: En `trackman_app.py`, borrar las 4 defs locales e importar de `core.hitting`**

Borrar `build_play_result_table`, `compute_plate_discipline_batter`, `build_split_table`,
`build_hitting_monthly` del monolito. Añadir al bloque de imports:
```python
from core.hitting import (build_play_result_table, compute_plate_discipline_batter,
                          build_split_table, build_hitting_monthly,
                          spray_points, hitting_summary)
```

- [ ] **Step 6: Verificar sintaxis + suite (core + regresión)**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -m pytest core/tests/ -q`

- [ ] **Step 7: Commit**

```bash
git add core/hitting.py core/tests/test_hitting.py trackman_app.py
git commit -m "feat: core/hitting — analítica de bateo + spray_points + hitting_summary"
```

---

### Task 2: `viz/hitting.py` — gráficos Plotly interactivos

**Files:**
- Create: `viz/hitting.py`, `viz/tests/test_hitting_viz.py`

**Interfaces:**
- Consumes: `viz.theme`, DataFrames de bateo.
- Produces: `ev_distribution(df, name)`, `la_distribution(df, name)`, `ev_la_scatter(df, name)`,
  `damage_zone(df, name)`, `rolling_ev(df, name, window=15)` → `go.Figure`.

- [ ] **Step 1: Smoke tests primero**

```python
import plotly.graph_objects as go
import pandas as pd
from viz import hitting as vh

def _bb():
    return pd.DataFrame({
        "ExitSpeed": [98, 104, 80, 95, 88, 101, 76], "Angle": [12, 28, -5, 20, 45, 15, 60],
        "PlateLocSide": [0.1, -0.2, 0.3, 0.0, 0.4, -0.1, 0.2],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.1, 3.0, 2.2, 2.5],
        "PlayResult": ["1B", "HR", "Out", "2B", "Out", "1B", "Out"],
        "PitchCall": ["InPlay"] * 7, "Date": pd.to_datetime(["2026-06-01"] * 7),
    })

def test_builders_return_figures_and_empty():
    for fn in (vh.ev_distribution, vh.la_distribution, vh.ev_la_scatter, vh.damage_zone, vh.rolling_ev):
        assert isinstance(fn(_bb(), "A"), go.Figure)
        f = fn(pd.DataFrame(), "A")
        assert isinstance(f, go.Figure) and f.layout.annotations
```

- [ ] **Step 2: Correr — deben fallar** (`ModuleNotFoundError: viz.hitting`)

- [ ] **Step 3: Crear `viz/hitting.py`**

```python
"""Constructores de figuras Plotly para el modo Hitting. DataFrame → go.Figure."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from viz import theme

RESULT_COLORS = {"1B": "#1DBE3A", "2B": "#00D1ED", "3B": "#9467bd", "HR": "#D22D49", "Out": "#8899a6"}

def ev_distribution(df, name):
    if "ExitSpeed" not in df.columns or df["ExitSpeed"].dropna().empty:
        return theme.empty_fig("No EV data")
    ev = df["ExitSpeed"].dropna()
    fig = go.Figure(go.Histogram(x=ev, nbinsx=24, marker_color=theme.GREY, opacity=0.85))
    fig.add_vline(x=95, line=dict(color="#D22D49", width=1.4, dash="dot"))
    fig.add_vline(x=float(ev.mean()), line=dict(color=theme.TEXT, width=1.6, dash="dash"))
    lay = theme.base_layout("Exit Velocity Distribution",
                            f"{name} · HH {int((ev>=95).sum())} ({round(100*(ev>=95).mean(),1)}%)")
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
                            f"{name} · sweet-spot {barrel} ({round(100*barrel/len(la),1)}%)")
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
    fig.add_shape(type="rect", x0=98, x1=118, y0=8, y1=32, line=dict(color="#1f77b4", width=1.5, dash="dash"),
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
    ev = loc["ExitSpeed"] if "ExitSpeed" in loc.columns else None
    fig = go.Figure(go.Scatter(
        x=loc["PlateLocSide"], y=loc["PlateLocHeight"], mode="markers",
        marker=dict(size=11, color=(ev if ev is not None else theme.GREY),
                    colorscale="RdBu_r" if ev is not None else None,
                    cmin=65, cmax=112, showscale=ev is not None,
                    colorbar=dict(title="EV") if ev is not None else None,
                    line=dict(width=0.6, color="white")),
        hovertemplate="EV %{marker.color:.1f}<br>%{x:.2f}, %{y:.2f}<extra></extra>" if ev is not None else None))
    lay = theme.base_layout("Damage Zone", f"{name} · dónde le pegan más duro")
    lay["shapes"] = theme.strike_zone_shapes()
    lay["xaxis"] = dict(range=[-2.0, 2.0], gridcolor=theme.GRID, zeroline=False)
    lay["yaxis"] = dict(range=[0.4, 4.6], gridcolor=theme.GRID, zeroline=False, scaleanchor="x", scaleratio=1)
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
```

- [ ] **Step 4: Correr los tests — deben pasar** (`.venv/bin/python -m pytest viz/tests/test_hitting_viz.py -v`)

- [ ] **Step 5: Commit**

```bash
git add viz/hitting.py viz/tests/test_hitting_viz.py
git commit -m "feat: viz/hitting — EV/LA dist, EV×LA scatter, damage zone, rolling EV (Plotly)"
```

---

### Task 3: Spray broadcast — `viz/spray_render.py` (matplotlib) + `spray_interactive` (Plotly)

**Files:**
- Create: `viz/spray_render.py`
- Modify: `viz/hitting.py` (añadir `spray_interactive`), `viz/tests/test_hitting_viz.py`, crear `viz/tests/test_spray_render.py`

**Interfaces:**
- Produces: `viz.spray_render.render_spray_png(points, summary, name, color_by="ev") -> bytes|None`;
  `viz.hitting.spray_interactive(points, name, color_by="ev") -> go.Figure`.
- `color_by ∈ {"ev","result"}`. `points`/`summary` de `core.hitting.spray_points`/`hitting_summary`.

- [ ] **Step 1: Smoke tests primero**

`viz/tests/test_spray_render.py`:
```python
import pandas as pd
from core.hitting import spray_points, hitting_summary
from viz import spray_render as sp

def _pts():
    df = pd.DataFrame({
        "ExitSpeed": [98, 104, 80, 95], "Angle": [12, 28, -5, 20],
        "Distance": [150, 410, 60, 330], "Bearing": [0, 10, -20, 25],
        "PlayResult": ["1B", "HR", "Out", "2B"], "PitchCall": ["InPlay"] * 4,
    })
    return spray_points(df), hitting_summary(df, {"ev_hard": 95})

def test_render_spray_png_ev_and_result():
    pts, s = _pts()
    for cb in ("ev", "result"):
        png = sp.render_spray_png(pts, s, "A", color_by=cb)
        assert isinstance(png, (bytes, bytearray)) and png[:8].startswith(b"\x89PNG")

def test_render_spray_png_empty():
    assert sp.render_spray_png({"points": []}, {}, "A") is None
```
Añadir a `viz/tests/test_hitting_viz.py`:
```python
def test_spray_interactive():
    from core.hitting import spray_points
    df = pd.DataFrame({"Distance": [150, 410], "Bearing": [0, 10], "ExitSpeed": [98, 104],
                       "Angle": [12, 28], "PlayResult": ["1B", "HR"], "PitchCall": ["InPlay"] * 2})
    pts = spray_points(df)
    assert isinstance(vh.spray_interactive(pts, "A", color_by="ev"), go.Figure)
    assert isinstance(vh.spray_interactive({"points": []}, "A"), go.Figure)
```

- [ ] **Step 2: Correr — deben fallar**

- [ ] **Step 3: Crear `viz/spray_render.py` (campo top-down foto-realista de día + panel)**

```python
"""Spray chart broadcast: campo top-down foto-realista (matplotlib) + panel de bateo. PNG bytes."""
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp

GRASS_A, GRASS_B = "#3f8c3a", "#4a9a44"    # franjas de corte
DIRT, TRACK = "#b07a4a", "#c9a06a"
WALL = "#20361f"
RESULT_COLORS = {"1B": "#1DBE3A", "2B": "#00D1ED", "3B": "#9467bd", "HR": "#D22D49", "Out": "#8899a6"}
FENCE_R = 340.0  # radio aprox de la barda (ft)

def _fence_xy(n=240):
    t = np.linspace(-45, 45, n)
    r = 330 + 70 * np.cos(np.deg2rad(t * 2))     # 330 en líneas, ~400 al CF
    return r * np.sin(np.deg2rad(t)), r * np.cos(np.deg2rad(t)), t, r

def _f(v, suf="", dec=1):
    return "—" if v is None else f"{v:.{dec}f}{suf}"

def render_spray_png(points, summary, name, color_by="ev"):
    pts = points.get("points", []) if points else []
    if not pts:
        return None
    fig = plt.figure(figsize=(9.5, 8.2), dpi=120)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0]); ax.set_axis_off()
    ax.set_xlim(-360, 360); ax.set_ylim(-40, 440); ax.set_aspect("equal")
    fx, fy, ft, fr = _fence_xy()
    # pasto (fan) con franjas de corte: cuñas radiales alternadas
    for i in range(len(ft) - 1):
        wedge = [(0, 0), (fx[i], fy[i]), (fx[i + 1], fy[i + 1])]
        ax.add_patch(mp.Polygon(wedge, closed=True,
                     color=GRASS_A if i % 2 else GRASS_B, zorder=0, lw=0))
    # warning track (anillo tan por dentro de la barda)
    tx = (fr - 12) * np.sin(np.deg2rad(ft)); ty = (fr - 12) * np.cos(np.deg2rad(ft))
    ax.fill(np.concatenate([fx, tx[::-1]]), np.concatenate([fy, ty[::-1]]),
            color=TRACK, zorder=1, lw=0)
    # barda
    ax.plot(fx, fy, color=WALL, lw=4, zorder=2, solid_capstyle="round")
    # infield de tierra (diamante + arco de tierra)
    d = 63.64
    inf_t = np.linspace(-45, 45, 80)
    arc_x = 95 * np.sin(np.deg2rad(inf_t)); arc_y = 95 * np.cos(np.deg2rad(inf_t))
    ax.fill(np.concatenate([[0], arc_x, [0]]), np.concatenate([[0], arc_y, [0]]),
            color=DIRT, zorder=2, lw=0)
    ax.add_patch(mp.Circle((0, 60.5), 9, facecolor=DIRT, edgecolor="none", zorder=3))
    # líneas de foul, plato, bases
    for sgn in (1, -1):
        ax.plot([0, sgn * 330 * np.sin(np.deg2rad(45))], [0, 330 * np.cos(np.deg2rad(45))],
                color="#f2f2f2", lw=2.0, zorder=4)
    ax.add_patch(mp.Polygon([(-3.5, 0), (3.5, 0), (3.5, -3.5), (0, -7), (-3.5, -3.5)],
                 closed=True, facecolor="white", edgecolor="#cfcfcf", lw=1, zorder=5))
    for bx, by in [(d, d), (0, 2 * d), (-d, d)]:
        ax.add_patch(mp.Rectangle((bx - 3, by - 3), 6, 6, angle=45, facecolor="white",
                     edgecolor="#cfcfcf", lw=1, zorder=5))
    # batazos
    xs = [p["x"] for p in pts]; ys = [p["y"] for p in pts]
    if color_by == "result":
        for res, col in RESULT_COLORS.items():
            gx = [p["x"] for p in pts if p["result"] == res]
            gy = [p["y"] for p in pts if p["result"] == res]
            if gx:
                ax.scatter(gx, gy, s=70, color=col, alpha=0.9, edgecolors="white",
                           linewidths=0.8, zorder=7, label=res)
        other = [(p["x"], p["y"]) for p in pts if p["result"] not in RESULT_COLORS]
        if other:
            ax.scatter([o[0] for o in other], [o[1] for o in other], s=34, color="#dddddd",
                       alpha=0.5, edgecolors="white", linewidths=0.4, zorder=6)
        ax.legend(loc="lower right", fontsize=9, framealpha=0.85)
    else:
        evs = [p["ev"] if p["ev"] is not None else np.nan for p in pts]
        sc = ax.scatter(xs, ys, c=evs, cmap="coolwarm", vmin=65, vmax=112, s=70, alpha=0.9,
                        edgecolors="white", linewidths=0.8, zorder=7)
        cb = fig.colorbar(sc, ax=ax, pad=0.01, shrink=0.5)
        cb.set_label("Exit Velocity (mph)", fontsize=9); cb.outline.set_visible(False)
    ax.text(0, 415, "400 ft", fontsize=8, color="#eef3ee", ha="center", zorder=6,
            path_effects=[])
    # panel de bateo (arriba-izquierda)
    s = summary or {}
    rows = [("Avg EV", _f(s.get("avg_ev"), " mph")), ("Max EV", _f(s.get("max_ev"), " mph")),
            ("Avg LA", _f(s.get("avg_la"), "°")), ("HH %", _f(s.get("hh_pct"), "%")),
            ("Barrel %", _f(s.get("barrel_pct"), "%")), ("wOBA", _f(s.get("woba"), "", 3))]
    ph = 0.055 * len(rows) + 0.10
    ax.add_patch(mp.FancyBboxPatch((0.015, 0.965 - ph), 0.30, ph, transform=ax.transAxes,
                 boxstyle="round,pad=0.008", facecolor="#8e0e24f0", edgecolor="#ffffff33",
                 lw=1.2, zorder=20))
    ax.text(0.03, 0.95, name, transform=ax.transAxes, fontsize=15, fontweight="bold",
            color="#fff", va="top", zorder=21)
    ax.text(0.03, 0.915, "BATTED BALL PROFILE", transform=ax.transAxes, fontsize=8,
            color="#ffffffcc", va="top", zorder=21)
    for i, (k, v) in enumerate(rows):
        y = 0.885 - i * 0.052
        ax.text(0.03, y, k.upper(), transform=ax.transAxes, fontsize=9.5, fontweight="bold",
                color="#fff", va="center", zorder=21)
        ax.text(0.30, y, v, transform=ax.transAxes, fontsize=9.5, color="#ffffffe6",
                va="center", ha="right", zorder=21)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor="#0e1a12")
    plt.close(fig); buf.seek(0)
    return buf.getvalue()
```

- [ ] **Step 4: Añadir `spray_interactive` a `viz/hitting.py`**

```python
def spray_interactive(points, name, color_by="ev"):
    """Spray Plotly interactivo: campo estilizado + scatter con hover. color_by ∈ {'ev','result'}."""
    pts = points.get("points", []) if points else []
    if not pts:
        return theme.empty_fig("No spray data")
    import numpy as np
    t = np.linspace(-45, 45, 120)
    r = 330 + 70 * np.cos(np.deg2rad(t * 2))
    fx = (r * np.sin(np.deg2rad(t))).tolist(); fy = (r * np.cos(np.deg2rad(t))).tolist()
    fig = go.Figure()
    # pasto (fan)
    fig.add_trace(go.Scatter(x=[0] + fx + [0], y=[0] + fy + [0], fill="toself",
        fillcolor="#e7f2e6", line=dict(color="#8bbf86", width=1), hoverinfo="skip", showlegend=False))
    # barda + foul
    fig.add_trace(go.Scatter(x=fx, y=fy, mode="lines", line=dict(color="#4a7c46", width=3),
        hoverinfo="skip", showlegend=False))
    for sgn in (1, -1):
        fig.add_trace(go.Scatter(x=[0, sgn * 330 * np.sin(np.deg2rad(45))], y=[0, 330 * np.cos(np.deg2rad(45))],
            mode="lines", line=dict(color="#b9c6b7", width=1.5), hoverinfo="skip", showlegend=False))
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

def _h(v):
    return "—" if v is None else f"{v:.1f}"
```

- [ ] **Step 5: Correr los tests — deben pasar** (`.venv/bin/python -m pytest viz/tests/ -q`)

- [ ] **Step 6: Commit**

```bash
git add viz/spray_render.py viz/hitting.py viz/tests/
git commit -m "feat: spray broadcast — render_spray_png (matplotlib top-down) + spray_interactive (Plotly)"
```

---

### Task 4: Rewire `render_hitting` + PDF + limpiar plots matplotlib

**Files:**
- Modify: `trackman_app.py` (`render_hitting`, imports; borrar plots matplotlib de hitting)

**Interfaces:**
- Consumes: `core.hitting.{spray_points, hitting_summary}`, `viz.hitting.*`, `viz.spray_render.render_spray_png`.

- [ ] **Step 1: Añadir imports en `trackman_app.py`**
```python
from viz import hitting as vhit
from viz.spray_render import render_spray_png
```

- [ ] **Step 2: Reescribir `render_hitting` (delgado)** — reemplazar la función completa (actual :1640-1756) por la versión que:
  - Usa `hitting_summary(bdf, lmeta)` para las 7 métricas de cabecera (Pitches/PA, Avg EV, Avg LA, HH%, Barrel%, wOBA, Dates). Conserva `compute_plate_discipline_batter` (ya importado de core) para los badges y `render_percentile_section`.
  - Tab **Monthly**: tabla + `st.plotly_chart(vhit.rolling_ev(bdf, selected))`.
  - Tab **Splits**: tabla; spray-by-hand con `st.image(render_spray_png(spray_points(sub_h), hitting_summary(sub_h, lmeta), f"{selected} vs {hand}", color_by=spray_color))`.
  - Tab **Results**: tabla.
  - Tab **Spray**: `st.radio` "Vista" (🖼️ Pro / 🔍 Interactivo, key `hit_spray_view`) + `st.radio` "Color" (Exit Velocity / Resultado, key `hit_spray_color`) → `cb = "ev" if color=="Exit Velocity" else "result"`. Pro → `st.image(render_spray_png(pts, summ, selected, color_by=cb))`; Interactivo → `st.plotly_chart(vhit.spray_interactive(pts, selected, color_by=cb))`. Debajo, `st.plotly_chart(vhit.damage_zone(bdf, selected))`.
  - Tab **Distributions**: `st.plotly_chart(vhit.ev_distribution(...))` + `la_distribution` + `ev_la_scatter`.
  - Tab **Stadium**: sin cambios.
  - **Export PDF**: construir las figuras Plotly (`ev`, `la`, `ev_la`, `damage`) + la spray Plotly y pasarlas a `export_hitting_pdf` (que ya soporta figuras Plotly vía `_fig_to_img`/kaleido desde iter 1). El spray del PDF usa `vhit.spray_interactive(pts, selected, color_by=cb)`.
  - Quitar la línea final `for f in [...]: plt.close(f)` (figuras Plotly).

  (El código completo se transcribe siguiendo el patrón de `render_pitching` de iter 1; usar los helpers arriba. Leer `render_pitching` como referencia de estilo.)

- [ ] **Step 3: Verificar sintaxis + import smoke + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`

- [ ] **Step 4: Borrar los plots matplotlib de hitting ya sin uso** (grep-guarded)

Confirmar que `plot_spray_chart`, `plot_ev_la_scatter`, `plot_damage_zone`, `plot_ev_distribution`,
`plot_la_distribution`, `plot_rolling_ev` no tienen otros call-sites (`grep -nE "plot_(spray_chart|ev_la_scatter|damage_zone|ev_distribution|la_distribution|rolling_ev)" trackman_app.py`), y borrarlas. Conservar helpers compartidos (`draw_savant_zone`, `draw_plate`, `style_zone_ax`, `setup_savant_fig`, `savant_title`, `zone_heatmap_ax`).

- [ ] **Step 5: Verificación funcional headless** (replica render_hitting) — construir un DataFrame de bateo y renderizar todos los builders + `render_spray_png` (ambos color_by) + `export_hitting_pdf` con las figuras Plotly; confirmar bytes/PDF válido. Ver Task 5.

- [ ] **Step 6: Commit**

```bash
git add trackman_app.py
git commit -m "feat: render_hitting en Plotly + spray broadcast (toggles) + PDF vía Plotly"
```

---

### Task 5: Verificación visual + tuning del spray + regresión + changelog (controller)

- [ ] **Step 1: Renderizar el spray a PNG** (por EV y por resultado) con un DataFrame realista y **verlo**; comparar con un spray de broadcast (campo diurno realista, batazos legibles, panel). Iterar colores/franjas/tamaños en `viz/spray_render.py`. Commit del tuning.
- [ ] **Step 2: Regresión completa** — `.venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`; import de `trackman_app`; smoke de los otros modos (Pitching/League/Top Plays/3D) sin romper.
- [ ] **Step 3: Changelog** en `README.md` (nueva entrada v4.12: Hitting interactivo + spray broadcast).
- [ ] **Step 4: Visto bueno del founder** (app corriendo o preview).
- [ ] **Step 5: Merge a `main`** (push → PR → merge → borrar rama → sync → tests en main).

---

## Self-Review

**1. Spec coverage:** core/hitting (mover + spray_points/hitting_summary) → Task 1. viz/hitting Plotly (5 gráficos) → Task 2. Spray broadcast estático + interactivo + toggles → Task 3+4. render_hitting delgado + PDF → Task 4. Verificación visual → Task 5. Tests → Tasks 1-3. ✓
**2. Placeholder scan:** Task 4 Step 2 describe la reescritura de `render_hitting` en prosa detallada (patrón de render_pitching) en vez de transcribir 100+ líneas — es el único paso sin bloque de código completo; referencia el patrón existente y todos los helpers/firmas. Aceptable por tamaño; el resto tiene código completo.
**3. Type consistency:** `spray_points`→dict `{"points":[{x,y,ev,la,distance,result}]}` consumido por `render_spray_png` y `spray_interactive`. `hitting_summary`→dict consumido por el panel. `color_by ∈ {"ev","result"}` consistente. Builders Plotly `(df,name)->go.Figure`. ✓

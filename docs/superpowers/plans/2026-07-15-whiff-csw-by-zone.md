# Whiff/CSW por Zona — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un grid interactivo 5×5 de Whiff%/CSW% por zona al modo Pitching, con selector de tipo de pitcheo y toggle de métrica, en un tab nuevo.

**Architecture:** Continúa el patrón de la iter 1: analítica pura en `core/pitching.py`, figura Plotly en `viz/pitching.py`, y `render_pitching` en `trackman_app.py` orquesta (core → viz → Streamlit).

**Tech Stack:** Python, pandas, numpy, Streamlit, Plotly, pytest.

## Global Constraints

- `core/` NO importa `streamlit` ni `matplotlib`. Solo `pandas`/`numpy` y otros `core`.
- `viz/` NO importa `streamlit`. Solo `plotly` (+ `numpy`/`pandas`) y `core`.
- `whiff_csw_zone_grid` es pura y NO requiere `TaggedPitchType` (el filtrado por tipo se hace en la UI antes de llamarla); no debe lanzar por su ausencia.
- `zone_rate_heatmap` degrada a `theme.empty_fig(...)` con grid vacío; nunca lanza.
- Whiff% = StrikeSwinging / swings (swings = `SWING_CALLS`); denominador = swings de la celda.
- CSW% = (StrikeCalled + StrikeSwinging) / pitcheos; denominador = pitcheos de la celda.
- Geometría: 3×3 interno alineado a la zona (`ZONE_HALF_WIDTH=0.83`, `ZONE_BOTTOM=1.5`, `ZONE_TOP=3.5`); celda uniforme = zona/3; banda externa (chase) captura lo de afuera por clamp.
- Guarda de muestra: celda confiable si Whiff ≥ `min_swings` (default 4) / CSW ≥ `min_pitches` (default 5).
- Tests desde la raíz con `.venv/bin/python -m pytest`. Rama: `iter2-whiff-csw-zone`. Un commit por tarea.

---

### Task 1: `core/pitching.py` — `whiff_csw_zone_grid`

**Files:**
- Modify: `core/pitching.py` (añadir función + su import de constantes)
- Modify: `core/tests/test_pitching.py` (añadir tests)

**Interfaces:**
- Consumes: `core.metrics.{safe_pct, SWING_CALLS, ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP}`
- Produces: `whiff_csw_zone_grid(df, min_swings=4, min_pitches=5) -> dict` con keys
  `x_edges` (6 floats), `z_edges` (6 floats), `cells` (lista de dicts con
  `ix, iz, n_pitches, n_swings, whiffs, called, whiff_pct, csw_pct, whiff_reliable, csw_reliable`),
  `total_pitches` (int).

- [ ] **Step 1: Escribir los tests primero**

Añadir a `core/tests/test_pitching.py`:

```python
from core.pitching import whiff_csw_zone_grid

def _cell(grid, ix, iz):
    return next(c for c in grid["cells"] if c["ix"] == ix and c["iz"] == iz)

def test_zone_grid_center_cell_rates():
    # Celda central (ix=2, iz=2): x∈[-0.277,0.277], z∈[2.167,2.833] → usar x=0, z=2.5
    df = pd.DataFrame({
        "PlateLocSide":  [0.0, 0.0, 0.0, 0.0],
        "PlateLocHeight":[2.5, 2.5, 2.5, 2.5],
        "PitchCall": ["StrikeSwinging", "StrikeSwinging", "FoulBall", "StrikeCalled"],
    })
    grid = whiff_csw_zone_grid(df)
    c = _cell(grid, 2, 2)
    assert c["n_pitches"] == 4
    assert c["n_swings"] == 3          # 2 StrikeSwinging + 1 FoulBall
    assert c["whiffs"] == 2
    assert c["called"] == 1
    assert c["whiff_pct"] == round(100 * 2 / 3, 1)      # whiffs/swings
    assert c["csw_pct"] == round(100 * (1 + 2) / 4, 1)  # (called+whiffs)/pitches

def test_zone_grid_reliability_flags():
    # 1 solo swing en una celda → whiff no confiable; <5 pitcheos → csw no confiable
    df = pd.DataFrame({
        "PlateLocSide": [0.0], "PlateLocHeight": [2.5],
        "PitchCall": ["StrikeSwinging"],
    })
    c = _cell(whiff_csw_zone_grid(df), 2, 2)
    assert c["whiff_reliable"] is False   # 1 swing < 4
    assert c["csw_reliable"] is False     # 1 pitch < 5

def test_zone_grid_outer_clamp():
    # Pitcheo muy afuera a la derecha (x=3.0) cae en la columna de borde ix=4;
    # muy abajo (z=0.2) cae en iz=0.
    df = pd.DataFrame({
        "PlateLocSide": [3.0], "PlateLocHeight": [0.2],
        "PitchCall": ["BallCalled"],
    })
    c = _cell(whiff_csw_zone_grid(df), 4, 0)
    assert c["n_pitches"] == 1

def test_zone_grid_inner_3x3_is_strike_zone():
    from core.metrics import ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP
    grid = whiff_csw_zone_grid(pd.DataFrame({"PlateLocSide": [], "PlateLocHeight": [], "PitchCall": []}))
    # bordes internos coinciden con la zona
    assert grid["x_edges"][1] == -ZONE_HALF_WIDTH
    assert grid["x_edges"][4] == ZONE_HALF_WIDTH
    assert grid["z_edges"][1] == ZONE_BOTTOM
    assert grid["z_edges"][4] == ZONE_TOP

def test_zone_grid_missing_columns_no_raise():
    assert whiff_csw_zone_grid(pd.DataFrame({"PlateLocSide": [0.0]}))["cells"] == []
    assert whiff_csw_zone_grid(pd.DataFrame())["cells"] == []
```

- [ ] **Step 2: Correr los tests — deben fallar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/test_pitching.py -k zone -v`
Expected: FAIL con `ImportError: cannot import name 'whiff_csw_zone_grid'`.

- [ ] **Step 3: Implementar `whiff_csw_zone_grid` en `core/pitching.py`**

Actualizar el import de `core.metrics` al inicio de `core/pitching.py` para incluir las constantes de zona:

```python
from core.metrics import (safe_pct, in_zone_mask, SWING_CALLS, CONTACT_CALLS,
                          ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP)
```

Añadir al final del archivo:

```python
def whiff_csw_zone_grid(df, min_swings=4, min_pitches=5):
    """Grid 5×5 de tasas Whiff%/CSW% por celda (vista catcher).

    El 3×3 interno se alinea a la zona de strike; la banda externa (una celda por
    lado) captura el área de chase — los pitcheos fuera del extent se asignan por
    clamp a la celda de borde. Puro; NO requiere TaggedPitchType (el filtrado por
    tipo se hace antes de llamar).
    """
    cell_x = (2 * ZONE_HALF_WIDTH) / 3.0
    cell_z = (ZONE_TOP - ZONE_BOTTOM) / 3.0
    x_edges = [-ZONE_HALF_WIDTH - cell_x, -ZONE_HALF_WIDTH, -ZONE_HALF_WIDTH + cell_x,
               ZONE_HALF_WIDTH - cell_x, ZONE_HALF_WIDTH, ZONE_HALF_WIDTH + cell_x]
    z_edges = [ZONE_BOTTOM - cell_z, ZONE_BOTTOM, ZONE_BOTTOM + cell_z,
               ZONE_TOP - cell_z, ZONE_TOP, ZONE_TOP + cell_z]
    empty = {"x_edges": x_edges, "z_edges": z_edges, "cells": [], "total_pitches": 0}
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns) or "PitchCall" not in df.columns:
        return empty
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        return empty
    pc = loc["PitchCall"].astype(str)
    # 5 celdas por eje: digitize contra los 4 bordes internos, clamp a 0..4
    xi = np.clip(np.digitize(loc["PlateLocSide"].to_numpy(), x_edges[1:5]), 0, 4)
    zi = np.clip(np.digitize(loc["PlateLocHeight"].to_numpy(), z_edges[1:5]), 0, 4)
    swing = pc.isin(SWING_CALLS).to_numpy()
    whiff = (pc == "StrikeSwinging").to_numpy()
    called = (pc == "StrikeCalled").to_numpy()
    cells = []
    for iz in range(5):
        for ix in range(5):
            m = (xi == ix) & (zi == iz)
            n = int(m.sum())
            ns = int(swing[m].sum())
            nw = int(whiff[m].sum())
            nc = int(called[m].sum())
            cells.append({
                "ix": ix, "iz": iz, "n_pitches": n, "n_swings": ns,
                "whiffs": nw, "called": nc,
                "whiff_pct": safe_pct(nw, ns), "csw_pct": safe_pct(nc + nw, n),
                "whiff_reliable": ns >= min_swings, "csw_reliable": n >= min_pitches,
            })
    return {"x_edges": x_edges, "z_edges": z_edges, "cells": cells, "total_pitches": int(len(loc))}
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/test_pitching.py -k zone -v`
Expected: 5 passed.

- [ ] **Step 5: Correr toda la suite de core (sin regresión)**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/ -q`
Expected: todos pasan.

- [ ] **Step 6: Commit**

```bash
git add core/pitching.py core/tests/test_pitching.py
git commit -m "feat: core whiff_csw_zone_grid — grid 5x5 de tasas por zona"
```

---

### Task 2: `viz/pitching.py` — `zone_rate_heatmap`

**Files:**
- Modify: `viz/pitching.py` (añadir función)
- Modify: `viz/tests/test_pitching_viz.py` (añadir smoke tests)

**Interfaces:**
- Consumes: dict de `core.pitching.whiff_csw_zone_grid`, `viz.theme.{base_layout, strike_zone_shapes, empty_fig, GRID}`
- Produces: `zone_rate_heatmap(grid, metric, name) -> go.Figure`, `metric ∈ {"whiff", "csw"}`.

- [ ] **Step 1: Escribir los smoke tests primero**

Añadir a `viz/tests/test_pitching_viz.py`:

```python
from core.pitching import whiff_csw_zone_grid

def _grid():
    df = pd.DataFrame({
        "PlateLocSide":  [0.0, 0.1, -0.1, 0.0, 0.5, -0.5],
        "PlateLocHeight":[2.5, 2.4, 2.6, 2.0, 3.0, 2.2],
        "PitchCall": ["StrikeSwinging", "FoulBall", "StrikeCalled", "InPlay",
                      "BallCalled", "StrikeSwinging"],
    })
    return whiff_csw_zone_grid(df)

def test_zone_rate_heatmap_whiff_and_csw():
    g = _grid()
    assert isinstance(vp.zone_rate_heatmap(g, "whiff", "P"), go.Figure)
    assert isinstance(vp.zone_rate_heatmap(g, "csw", "P"), go.Figure)

def test_zone_rate_heatmap_empty_degrades():
    empty = whiff_csw_zone_grid(pd.DataFrame())
    f = vp.zone_rate_heatmap(empty, "whiff", "P")
    assert isinstance(f, go.Figure)
    assert f.layout.annotations  # empty_fig añade una anotación
```

- [ ] **Step 2: Correr — deben fallar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest viz/tests/test_pitching_viz.py -k zone_rate -v`
Expected: FAIL con `AttributeError: module 'viz.pitching' has no attribute 'zone_rate_heatmap'`.

- [ ] **Step 3: Implementar `zone_rate_heatmap` en `viz/pitching.py`**

Añadir al final de `viz/pitching.py`:

```python
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
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest viz/tests/test_pitching_viz.py -q`
Expected: todos los smoke de viz pasan (incluidos los nuevos zone_rate).

- [ ] **Step 5: Commit**

```bash
git add viz/pitching.py viz/tests/test_pitching_viz.py
git commit -m "feat: viz zone_rate_heatmap — grid interactivo Whiff/CSW por zona"
```

---

### Task 3: `trackman_app.py` — tab "🎯 Whiff/CSW" en `render_pitching`

**Files:**
- Modify: `trackman_app.py` (import + tab nuevo en `render_pitching`)

**Interfaces:**
- Consumes: `core.pitching.whiff_csw_zone_grid`, `viz.pitching.zone_rate_heatmap`

- [ ] **Step 1: Añadir `whiff_csw_zone_grid` al import de `core.pitching`**

En `trackman_app.py`, la línea (actualmente):
```python
from core.pitching import (build_usage_by_count, arsenal_stuff, movement_points)
```
cambiarla a:
```python
from core.pitching import (build_usage_by_count, arsenal_stuff, movement_points,
                           whiff_csw_zone_grid)
```

- [ ] **Step 2: Cambiar la línea de `st.tabs` para 5 tabs**

En `render_pitching`, la línea:
```python
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Summary", "📍 Location", "📊 Trends", "🏟️ Stadium"])
```
cambiarla a:
```python
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 Summary", "📍 Location", "📊 Trends", "🎯 Whiff/CSW", "🏟️ Stadium"])
```

- [ ] **Step 3: Renombrar el bloque Stadium de `tab4` a `tab5` e insertar el tab Whiff/CSW como `tab4`**

El bloque actual del Stadium es:
```python
    with tab4:
        st.info("Stadium analysis coming soon.")
```
Reemplazarlo por (el nuevo tab4 Whiff/CSW seguido del Stadium ahora en tab5):
```python
    with tab4:
        st.markdown('<div class="sh">🎯 Whiff% / CSW% por zona</div>', unsafe_allow_html=True)
        ptypes = ["Todos"] + sorted(pf["TaggedPitchType"].dropna().unique().tolist())
        cq1, cq2 = st.columns([2, 3])
        with cq1:
            sel_pt = st.selectbox("Tipo de pitcheo", ptypes, key="whiffcsw_ptype")
        with cq2:
            sel_metric = st.radio("Métrica", ["Whiff %", "CSW %"], key="whiffcsw_metric",
                                  horizontal=True)
        sub = pf if sel_pt == "Todos" else pf[pf["TaggedPitchType"] == sel_pt]
        grid = whiff_csw_zone_grid(sub)
        metric = "whiff" if sel_metric == "Whiff %" else "csw"
        st.plotly_chart(vpitch.zone_rate_heatmap(grid, metric, f"{selected} · {sel_pt}"),
                        use_container_width=True)
        st.caption(f"{grid['total_pitches']} pitcheos con ubicación · "
                   "celdas con muestra baja (Whiff <4 swings / CSW <5 pitcheos) en gris con solo el conteo.")
    with tab5:
        st.info("Stadium analysis coming soon.")
```

- [ ] **Step 4: Verificar sintaxis + import smoke**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('syntax ok')" && .venv/bin/python -c "import trackman_app; print('import ok')"`
Expected: "syntax ok" y "import ok" (warnings de streamlit bare-mode en stderr son normales; exit 0).

- [ ] **Step 5: Correr toda la suite (sin regresión)**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: todos pasan.

- [ ] **Step 6: Verificación funcional headless (opcional pero recomendada)**

Correr un smoke que replica el flujo del tab con un DataFrame sintético:
```bash
cd /Users/joseramirez/trackman-analayzer && .venv/bin/python - <<'PY'
import numpy as np, pandas as pd
from core.pitching import whiff_csw_zone_grid
from viz import pitching as vp
np.random.seed(1); n=200
df = pd.DataFrame({
    "TaggedPitchType": np.random.choice(["Fastball","Slider"], n),
    "PlateLocSide": np.random.randn(n)*0.6,
    "PlateLocHeight": 2.5+np.random.randn(n)*0.6,
    "PitchCall": np.random.choice(
        ["StrikeSwinging","StrikeCalled","FoulBall","InPlay","BallCalled"], n),
})
g = whiff_csw_zone_grid(df)
print("total_pitches:", g["total_pitches"], "cells:", len(g["cells"]))
for metric in ("whiff","csw"):
    f = vp.zone_rate_heatmap(g, metric, "Test")
    print(metric, "-> traces:", len(f.data), "annotations:", len(f.layout.annotations))
PY
```
Expected: `total_pitches` ~200, 25 cells, y ambas métricas producen una figura con traces y anotaciones.

- [ ] **Step 7: Commit**

```bash
git add trackman_app.py
git commit -m "feat: tab Whiff/CSW por zona en render_pitching (selector tipo + toggle)"
```

---

## Self-Review

**1. Spec coverage:**
- `whiff_csw_zone_grid` (grid 5×5, geometría zona-alineada, clamp, reliability, denominadores por métrica) → Task 1. ✓
- `zone_rate_heatmap` (heatmap por tasa, celdas no confiables en gris, overlay de zona, hover, degrada) → Task 2. ✓
- Tab "🎯 Whiff/CSW" con selector de tipo (+ Todos) y toggle Whiff/CSW → Task 3. ✓
- Guarda de muestra mínima (Whiff ≥4 swings, CSW ≥5 pitcheos) → Task 1 (flags) + Task 2 (render gris). ✓
- No-goals respetados (solo Pitching, sin PDF del grid, sin small-multiples). ✓
- Tests: core (tasas, reliability, clamp, geometría, sin columnas) + viz smoke → Tasks 1, 2. ✓

**2. Placeholder scan:** Sin TBD/TODO; todo el código nuevo está completo.

**3. Type consistency:** `whiff_csw_zone_grid` retorna el dict con las keys que `zone_rate_heatmap` consume (`cells`, `x_edges`, `z_edges`, y por celda `ix/iz/n_pitches/n_swings/whiffs/called/whiff_pct/csw_pct/whiff_reliable/csw_reliable`). El tab pasa `metric ∈ {"whiff","csw"}` que el builder espera. ✓

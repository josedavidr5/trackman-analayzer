# Pitching Interactivo + Panel de Arsenal "Stuff" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraer la analítica de Pitching a paquetes limpios (`core/`, `viz/`), migrar sus 6 gráficos a Plotly interactivo, y añadir el Panel de Arsenal "Stuff" (con CSW%), sin romper los demás modos.

**Architecture:** Enfoque "híbrido por fases": `core/` = analítica pura (pandas/numpy, cero Streamlit/matplotlib); `viz/` = constructores de figuras Plotly; `trackman_app.py` orquesta (`core` → `viz` → Streamlit). Mismo patrón que el paquete `trajectory/` ya existente.

**Tech Stack:** Python, pandas, numpy, Streamlit, Plotly, kaleido (PDF), pytest.

## Global Constraints

- `core/` NO importa `streamlit` ni `matplotlib`. Solo `pandas`/`numpy`.
- `viz/` NO importa `streamlit`. Solo `plotly` (+ `numpy`/`pandas`) y `core`.
- Ningún módulo nuevo importa assets externos (self-contained).
- Los primitivos compartidos se **mueven** (no se copian) del monolito a `core/`; el monolito los importa.
- Comandos de test desde la raíz del repo con `python -m pytest` (añade la raíz a `sys.path`).
- Commits frecuentes, uno por tarea. Rama de trabajo: `iter1-pitching-interactive-arsenal`.
- CSW% = (StrikeCalled + StrikeSwinging) / pitcheos del tipo. Whiff% = StrikeSwinging / swings (swings = `SWING_CALLS`).
- Cada builder de `viz/` maneja datos faltantes devolviendo `theme.empty_fig(mensaje)`; nunca lanza.

---

### Task 1: Scaffold `core/` + mover primitivos compartidos a `core/metrics.py`

**Files:**
- Create: `core/__init__.py`
- Create: `core/metrics.py`
- Create: `core/tests/__init__.py`
- Create: `core/tests/test_metrics.py`
- Modify: `trackman_app.py` (borrar defs locales, añadir import)

**Interfaces:**
- Produces: `core.metrics.pitch_color(pt, idx=0) -> str`, `safe_pct(num, denom) -> float`,
  `count_pa(df) -> int`, `in_zone_mask(df) -> (pd.Series, bool)`, `batted_ball_mask(df) -> pd.Series`,
  `barrel_mask(df, barrel_ev_base=98) -> pd.Series`, `count_k_bb(df) -> (int, int)`,
  `compute_woba(df) -> float`, y constantes `STATCAST_PITCH_COLORS`, `PITCH_PALETTE`,
  `TERMINAL_RESULTS`, `SWING_CALLS`, `CONTACT_CALLS`, `ZONE_HALF_WIDTH`, `ZONE_BOTTOM`,
  `ZONE_TOP`, `WOBA_W`.

- [ ] **Step 1: Crear `core/__init__.py` (vacío) y `core/tests/__init__.py` (vacío)**

```python
# core/__init__.py
```
```python
# core/tests/__init__.py
```

- [ ] **Step 2: Crear `core/metrics.py` con los primitivos (bodies verbatim del monolito)**

```python
"""Primitivos sabermétricos puros — sin Streamlit ni matplotlib. Solo pandas/numpy."""
import numpy as np
import pandas as pd

# ── Colores Statcast por tipo de pitcheo (hex literal; espejo del theme del app) ──
STATCAST_PITCH_COLORS = {
    "4-Seam": "#D22D49", "Fastball": "#D22D49", "2-Seam": "#DE6A04", "Sinker": "#FE9D00",
    "Cutter": "#933F2C", "Slider": "#C3BD0E", "Sweeper": "#DDB33A", "Curve": "#00D1ED",
    "Knuckle Curve": "#6236CD", "Change": "#1DBE3A", "Split": "#3BACAC",
    "Knuckleball": "#3C44CD", "Screwball": "#60DB33",
}
PITCH_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b",
                 "#e377c2", "#7f7f7f", "#2ca02c", "#ff9896", "#98df8a", "#c5b0d5"]

def pitch_color(pt, idx=0):
    return STATCAST_PITCH_COLORS.get(str(pt), PITCH_PALETTE[idx % len(PITCH_PALETTE)])

def safe_pct(num, denom):
    return round(100 * num / denom, 1) if denom > 0 else 0.0

TERMINAL_RESULTS = {"1B", "2B", "3B", "HR", "Out", "K", "BB", "HBP", "FC", "Error", "SacFly", "SacBunt"}
SWING_CALLS = {"StrikeSwinging", "FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "InPlay"}
CONTACT_CALLS = {"FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "InPlay"}
ZONE_HALF_WIDTH = 0.83
ZONE_BOTTOM, ZONE_TOP = 1.5, 3.5
WOBA_W = {"BB": 0.69, "HBP": 0.72, "1B": 0.89, "2B": 1.27, "3B": 1.62, "HR": 2.10}

def count_pa(df):
    """Plate appearances = pitches whose PlayResult is a terminal outcome."""
    if "PlayResult" in df.columns:
        pa = int(df["PlayResult"].astype(str).isin(TERMINAL_RESULTS).sum())
        if pa > 0:
            return pa
    if "PitchCall" in df.columns:
        return int(df["PitchCall"].astype(str).isin({"InPlay", "HitByPitch"}).sum())
    return 0

def in_zone_mask(df):
    """(mask, has_location) — true strike-zone membership from PlateLoc columns."""
    if {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns) and df["PlateLocSide"].notna().any():
        m = ((df["PlateLocSide"].abs() <= ZONE_HALF_WIDTH)
             & (df["PlateLocHeight"].between(ZONE_BOTTOM, ZONE_TOP)))
        return m.fillna(False), True
    return pd.Series(False, index=df.index), False

def batted_ball_mask(df):
    """Balls put in play — denominator for HH% / Barrel%."""
    if "PitchCall" in df.columns:
        m = df["PitchCall"].astype(str).eq("InPlay")
        if m.any():
            return m
    if "ExitSpeed" in df.columns:
        return df["ExitSpeed"].notna()
    return pd.Series(False, index=df.index)

def barrel_mask(df, barrel_ev_base=98):
    """Savant-style barrel window, rescaled by barrel_ev_base for amateur levels."""
    if not {"ExitSpeed", "Angle"}.issubset(df.columns):
        return pd.Series(False, index=df.index)
    ev = df["ExitSpeed"] + (98 - barrel_ev_base)
    la = df["Angle"]
    lo = (26 - (ev - 98)).clip(lower=8)
    hi = (30 + (ev - 98) * (20 / 18)).clip(upper=50)
    return ((ev >= 98) & (la >= lo) & (la <= hi)).fillna(False)

def count_k_bb(df):
    """(K, BB) counted once per PA from PlayResult, PitchCall fallback for K."""
    kk = bb = 0
    if "PlayResult" in df.columns:
        pr = df["PlayResult"].astype(str)
        kk = int(pr.eq("K").sum()); bb = int(pr.eq("BB").sum())
    if kk == 0 and "PitchCall" in df.columns:
        kk = int(df["PitchCall"].astype(str).isin({"StrikeoutSwinging", "StrikeoutCalled"}).sum())
    return kk, bb

def compute_woba(df):
    """wOBA from tagged PlayResults. Returns np.nan without PA data."""
    pa = count_pa(df)
    if pa == 0 or "PlayResult" not in df.columns:
        return np.nan
    pr = df["PlayResult"].astype(str)
    num = sum(w * int(pr.eq(res).sum()) for res, w in WOBA_W.items())
    denom = pa - int(pr.eq("SacBunt").sum())
    return round(num / denom, 3) if denom > 0 else np.nan
```

- [ ] **Step 3: Escribir tests en `core/tests/test_metrics.py`**

```python
import numpy as np
import pandas as pd
from core.metrics import (pitch_color, safe_pct, count_pa, in_zone_mask,
                          batted_ball_mask, barrel_mask, count_k_bb)

def test_safe_pct_zero_denom():
    assert safe_pct(5, 0) == 0.0
    assert safe_pct(1, 4) == 25.0

def test_pitch_color_known_and_fallback():
    assert pitch_color("Slider") == "#C3BD0E"
    assert pitch_color("MysteryPitch", 0) == "#1f77b4"

def test_count_pa_from_playresult():
    df = pd.DataFrame({"PlayResult": ["1B", "Out", "Undefined", "HR", "K"]})
    assert count_pa(df) == 4  # 1B, Out, HR, K (Undefined no cuenta)

def test_in_zone_mask_true_location():
    df = pd.DataFrame({"PlateLocSide": [0.0, 1.5], "PlateLocHeight": [2.5, 2.5]})
    mask, has_loc = in_zone_mask(df)
    assert has_loc is True
    assert mask.tolist() == [True, False]

def test_batted_ball_mask_inplay():
    df = pd.DataFrame({"PitchCall": ["InPlay", "BallCalled", "InPlay"]})
    assert batted_ball_mask(df).tolist() == [True, False, True]

def test_barrel_mask_basic():
    df = pd.DataFrame({"ExitSpeed": [100.0, 80.0], "Angle": [28.0, 28.0]})
    assert barrel_mask(df).tolist() == [True, False]

def test_count_k_bb():
    df = pd.DataFrame({"PlayResult": ["K", "BB", "K", "1B"]})
    assert count_k_bb(df) == (2, 1)
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest core/tests/test_metrics.py -v`
Expected: 7 passed.

- [ ] **Step 5: En `trackman_app.py`, borrar las defs locales y añadir el import**

Borrar del monolito las definiciones locales de (por nombre): `pitch_color` (y las constantes `STATCAST_PITCH_COLORS`, `PITCH_PALETTE`), `safe_pct`, `count_pa`, `in_zone_mask`, `batted_ball_mask`, `barrel_mask`, `count_k_bb`, `compute_woba`, y las constantes `TERMINAL_RESULTS`, `SWING_CALLS`, `CONTACT_CALLS`, `ZONE_HALF_WIDTH`, `ZONE_BOTTOM`, `ZONE_TOP`, `WOBA_W`. **Conservar** `SAVANT_BLUE..SAVANT_TEXT` (las usa matplotlib) y `_PCT_CMAP`.

Añadir cerca de los imports superiores (después de la línea `import ...` existente):

```python
from core.metrics import (
    STATCAST_PITCH_COLORS, PITCH_PALETTE, pitch_color, safe_pct,
    TERMINAL_RESULTS, SWING_CALLS, CONTACT_CALLS,
    ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP, WOBA_W,
    count_pa, in_zone_mask, batted_ball_mask, barrel_mask, count_k_bb, compute_woba,
)
```

- [ ] **Step 6: Verificar que el app importa y los tests globales pasan**

Run: `cd /Users/joseramirez/trackman-analayzer && python -c "import ast; ast.parse(open('trackman_app.py').read()); print('syntax ok')" && python -m pytest core/tests/ trajectory/tests/ -q`
Expected: "syntax ok" y todos los tests (7 nuevos + 18 de trajectory) pasan.

- [ ] **Step 7: Commit**

```bash
git add core/ trackman_app.py
git commit -m "refactor: extraer primitivos sabermétricos a core/metrics.py"
```

---

### Task 2: `core/pitching.py` — métricas de pitching + arsenal_stuff + movement_points

**Files:**
- Create: `core/pitching.py`
- Create: `core/tests/test_pitching.py`
- Modify: `trackman_app.py` (borrar `build_pitch_summary`, `compute_pitch_discipline`, `build_usage_by_count`; importar de `core.pitching`)

**Interfaces:**
- Consumes: `core.metrics.{safe_pct, in_zone_mask, SWING_CALLS, CONTACT_CALLS}`
- Produces:
  - `pitch_summary(df) -> pd.DataFrame` (cols: Pitch, Count, Usage %, Avg mph, Max mph, Spin, IVB, HB)
  - `pitch_discipline(df) -> pd.DataFrame` (cols: Pitch, Count, Zone %, Swing %, Contact %, Chase %, Whiff %)
  - `build_usage_by_count(df) -> pd.DataFrame` (rows=tipo, cols=conteo, valores=usage%)
  - `arsenal_stuff(df) -> pd.DataFrame` (cols: Pitch, Usage %, Count, Avg mph, Max mph, Spin, IVB, HB, Zone %, Swing %, Chase %, Whiff %, CSW %)
  - `movement_points(df) -> dict` con keys `"pitches"` (lista de {pitch_type,hb,ivb}) y `"centroids"` (lista de {pitch_type,hb,ivb,n,usage,avg_velo,max_velo,avg_spin,whiff,csw})

- [ ] **Step 1: Escribir el test primero — CSW%, arsenal_stuff, movement_points**

```python
import numpy as np
import pandas as pd
import pytest
from core.pitching import (pitch_summary, pitch_discipline, arsenal_stuff, movement_points)

def _df():
    # 4 sliders: 1 StrikeCalled, 1 StrikeSwinging, 1 FoulBall, 1 BallCalled
    return pd.DataFrame({
        "TaggedPitchType": ["Slider"] * 4 + ["Fastball"] * 2,
        "PitchCall": ["StrikeCalled", "StrikeSwinging", "FoulBall", "BallCalled",
                      "InPlay", "StrikeSwinging"],
        "RelSpeed": [84, 85, 84, 86, 94, 95],
        "SpinRate": [2400, 2410, 2390, 2405, 2200, 2210],
        "HorzBreak": [6, 7, 6.5, 6, -8, -8.5],
        "InducedVertBreak": [2, 2.5, 2.2, 2.1, 16, 16.5],
        "PlateLocSide": [0.1, 0.2, 0.0, 1.6, -0.1, 0.0],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.5, 2.5, 2.4],
    })

def test_csw_pct_slider():
    stuff = arsenal_stuff(_df())
    row = stuff[stuff["Pitch"] == "Slider"].iloc[0]
    # CSW = (StrikeCalled + StrikeSwinging) / 4 = 2/4 = 50.0
    assert row["CSW %"] == 50.0

def test_whiff_pct_slider():
    stuff = arsenal_stuff(_df())
    row = stuff[stuff["Pitch"] == "Slider"].iloc[0]
    # swings = StrikeSwinging + FoulBall + InPlay = 2; whiffs = 1 → 50.0
    assert row["Whiff %"] == 50.0

def test_arsenal_stuff_shape():
    stuff = arsenal_stuff(_df())
    assert set(stuff["Pitch"]) == {"Slider", "Fastball"}
    for c in ["Usage %", "Avg mph", "IVB", "HB", "Whiff %", "CSW %"]:
        assert c in stuff.columns

def test_movement_points_centroid():
    mp = movement_points(_df())
    cents = {c["pitch_type"]: c for c in mp["centroids"]}
    assert cents["Fastball"]["hb"] == pytest.approx(-8.25)
    assert cents["Fastball"]["ivb"] == pytest.approx(16.25)
    assert cents["Slider"]["n"] == 4
    assert sum(c["usage"] for c in mp["centroids"]) == pytest.approx(100.0, abs=0.2)

def test_empty_inputs_dont_crash():
    empty = pd.DataFrame({"TaggedPitchType": []})
    assert arsenal_stuff(empty).empty
    assert movement_points(empty) == {"pitches": [], "centroids": []}
```

- [ ] **Step 2: Correr el test — debe fallar (módulo inexistente)**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest core/tests/test_pitching.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'core.pitching'`.

- [ ] **Step 3: Crear `core/pitching.py`**

```python
"""Analítica de pitching pura — pandas/numpy. Sin Streamlit ni matplotlib."""
import numpy as np
import pandas as pd
from core.metrics import safe_pct, in_zone_mask, SWING_CALLS, CONTACT_CALLS

def pitch_summary(df):
    """Por tipo: Count, Usage %, Avg/Max mph, Spin, IVB, HB. FB primero, luego por Count."""
    total = len(df); rows = []
    for pt, grp in df.groupby("TaggedPitchType"):
        r = {"Pitch": pt, "Count": len(grp), "Usage %": safe_pct(len(grp), total)}
        if "RelSpeed" in grp.columns:
            r["Avg mph"] = round(grp["RelSpeed"].mean(), 1)
            r["Max mph"] = round(grp["RelSpeed"].max(), 1)
        for col, alias in [("SpinRate", "Spin"), ("InducedVertBreak", "IVB"), ("HorzBreak", "HB")]:
            r[alias] = round(grp[col].mean(), 1) if col in grp.columns else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_fb"] = out["Pitch"].str.lower().str.contains("fastball|4-seam|2-seam").astype(int)
    return out.sort_values(["_fb", "Count"], ascending=[False, False]).drop(columns="_fb").reset_index(drop=True)

def pitch_discipline(df):
    """Por tipo: Zone %, Swing %, Contact %, Chase %, Whiff %. Ubicación real si existe."""
    if "PitchCall" not in df.columns:
        return pd.DataFrame()
    ZONE_CALLS = {"StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallFieldable",
                  "FoulBallNotFieldable", "InPlay"}
    rows = []
    for pt, grp in df.groupby("TaggedPitchType"):
        pc = grp["PitchCall"].astype(str)
        n = len(grp)
        sw_m = pc.isin(SWING_CALLS); ct_m = pc.isin(CONTACT_CALLS); wh_m = pc.eq("StrikeSwinging")
        sw, ct, wh = int(sw_m.sum()), int(ct_m.sum()), int(wh_m.sum())
        zone_m, has_loc = in_zone_mask(grp)
        if has_loc:
            located = grp["PlateLocSide"].notna() & grp["PlateLocHeight"].notna()
            n_loc = int(located.sum()); in_z = int(zone_m.sum())
            oz = located & ~zone_m
            zone_pct = safe_pct(in_z, n_loc)
            chase_pct = safe_pct(int((sw_m & oz).sum()), max(int(oz.sum()), 1))
        else:
            in_z = int(pc.isin(ZONE_CALLS).sum())
            zone_pct = safe_pct(in_z, n)
            chase_pct = safe_pct(max(0, sw - ct), max(n - in_z, 1))
        rows.append({"Pitch": pt, "Count": n, "Zone %": zone_pct, "Swing %": safe_pct(sw, n),
                     "Contact %": safe_pct(ct, max(sw, 1)), "Chase %": chase_pct,
                     "Whiff %": safe_pct(wh, max(sw, 1))})
    return pd.DataFrame(rows).sort_values("Count", ascending=False).reset_index(drop=True)

def build_usage_by_count(df):
    """Usage % por conteo balls-strikes (rows=tipo, cols=conteo)."""
    if "Count" not in df.columns or df["Count"].isna().all():
        return pd.DataFrame()
    sub = df[df["Count"].notna() & ~df["Count"].astype(str).str.contains("<NA>", na=True)]
    if sub.empty:
        return pd.DataFrame()
    order = [f"{b}-{s}" for b in range(4) for s in range(3)]
    tab = pd.crosstab(sub["TaggedPitchType"], sub["Count"], normalize="columns") * 100
    cols = [c for c in order if c in tab.columns]
    return tab[cols].round(1) if cols else pd.DataFrame()

def _csw_pct(pc):
    """CSW% = (StrikeCalled + StrikeSwinging) / pitcheos, de una Serie PitchCall."""
    return safe_pct(int(pc.isin({"StrikeCalled", "StrikeSwinging"}).sum()), len(pc))

def arsenal_stuff(df):
    """Una fila por tipo: usage, velo, spin, movimiento, disciplina + CSW%."""
    summ = pitch_summary(df)
    if summ.empty:
        return summ
    disc = pitch_discipline(df)
    disc_by = {r["Pitch"]: r for r in disc.to_dict("records")} if not disc.empty else {}
    has_pc = "PitchCall" in df.columns
    rows = []
    for r in summ.to_dict("records"):
        pt = r["Pitch"]; d = disc_by.get(pt, {})
        pc = (df[df["TaggedPitchType"] == pt]["PitchCall"].astype(str)
              if has_pc else pd.Series(dtype=str))
        rows.append({
            "Pitch": pt, "Usage %": r.get("Usage %", 0.0), "Count": r.get("Count", 0),
            "Avg mph": r.get("Avg mph", np.nan), "Max mph": r.get("Max mph", np.nan),
            "Spin": r.get("Spin", np.nan), "IVB": r.get("IVB", np.nan), "HB": r.get("HB", np.nan),
            "Zone %": d.get("Zone %", np.nan), "Swing %": d.get("Swing %", np.nan),
            "Chase %": d.get("Chase %", np.nan), "Whiff %": d.get("Whiff %", np.nan),
            "CSW %": _csw_pct(pc) if has_pc and len(pc) else np.nan,
        })
    return pd.DataFrame(rows)

def _fnum(v):
    return float(v) if v is not None and pd.notna(v) else None

def movement_points(df):
    """Puntos individuales (hb,ivb) + centroide por tipo enriquecido con arsenal_stuff."""
    out = {"pitches": [], "centroids": []}
    if not {"HorzBreak", "InducedVertBreak"}.issubset(df.columns):
        return out
    sub = df.dropna(subset=["HorzBreak", "InducedVertBreak"])
    if sub.empty:
        return out
    stuff = {r["Pitch"]: r for r in arsenal_stuff(df).to_dict("records")}
    for pt, g in sub.groupby("TaggedPitchType"):
        for hb, ivb in zip(g["HorzBreak"], g["InducedVertBreak"]):
            out["pitches"].append({"pitch_type": pt, "hb": float(hb), "ivb": float(ivb)})
        s = stuff.get(pt, {})
        out["centroids"].append({
            "pitch_type": pt, "hb": float(g["HorzBreak"].mean()),
            "ivb": float(g["InducedVertBreak"].mean()), "n": int(len(g)),
            "usage": float(s.get("Usage %", 0.0)), "avg_velo": _fnum(s.get("Avg mph")),
            "max_velo": _fnum(s.get("Max mph")), "avg_spin": _fnum(s.get("Spin")),
            "whiff": _fnum(s.get("Whiff %")), "csw": _fnum(s.get("CSW %")),
        })
    return out
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest core/tests/test_pitching.py -v`
Expected: 6 passed.

- [ ] **Step 5: Test de regresión — la extracción no cambió resultados**

Añadir a `core/tests/test_pitching.py`:

```python
def test_regression_matches_monolith_summary():
    # pitch_summary debe igualar el cálculo directo por grupos
    df = _df()
    summ = pitch_summary(df)
    fb = summ[summ["Pitch"] == "Fastball"].iloc[0]
    assert fb["Count"] == 2
    assert fb["Usage %"] == round(100 * 2 / 6, 1)
    assert fb["Avg mph"] == 94.5
```

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest core/tests/test_pitching.py -q`
Expected: 7 passed.

- [ ] **Step 6: En `trackman_app.py`, borrar `build_pitch_summary`, `compute_pitch_discipline`, `build_usage_by_count` e importar de `core.pitching`**

Borrar las tres defs locales. Añadir al bloque de imports:

```python
from core.pitching import (build_usage_by_count, arsenal_stuff, movement_points)
from core.pitching import pitch_summary as build_pitch_summary
from core.pitching import pitch_discipline as compute_pitch_discipline
```

(Los alias `build_pitch_summary`/`compute_pitch_discipline` mantienen los call-sites existentes en `render_pitching` funcionando sin tocarlos todavía; se limpian en la Task 8.)

- [ ] **Step 7: Verificar sintaxis y tests globales**

Run: `cd /Users/joseramirez/trackman-analayzer && python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && python -m pytest core/tests/ trajectory/tests/ -q`
Expected: "ok" y todo pasa.

- [ ] **Step 8: Commit**

```bash
git add core/pitching.py core/tests/test_pitching.py trackman_app.py
git commit -m "feat: core/pitching con arsenal_stuff (CSW%) y movement_points"
```

---

### Task 3: `viz/theme.py` — tema Plotly estilo Savant

**Files:**
- Create: `viz/__init__.py`
- Create: `viz/theme.py`
- Create: `viz/tests/__init__.py`
- Create: `viz/tests/test_theme.py`

**Interfaces:**
- Consumes: `core.metrics.{pitch_color, ZONE_HALF_WIDTH, ZONE_BOTTOM, ZONE_TOP}`
- Produces: `viz.theme.{BG, GRID, TEXT, GREY, color_map(types)->dict, strike_zone_shapes()->list,
  home_plate_shape()->dict, movement_rings()->list, base_layout(title, subtitle="")->dict,
  empty_fig(msg)->go.Figure}`

- [ ] **Step 1: Crear `viz/__init__.py` y `viz/tests/__init__.py` (vacíos)**

```python
# viz/__init__.py
```
```python
# viz/tests/__init__.py
```

- [ ] **Step 2: Escribir el test primero — `viz/tests/test_theme.py`**

```python
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
```

- [ ] **Step 3: Correr el test — debe fallar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_theme.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'viz.theme'`.

- [ ] **Step 4: Crear `viz/theme.py`**

```python
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
```

- [ ] **Step 5: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_theme.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add viz/__init__.py viz/theme.py viz/tests/
git commit -m "feat: viz/theme — tema Plotly estilo Savant"
```

---

### Task 4: `viz/pitching.py` — movement_bubble (Panel de Arsenal)

**Files:**
- Create: `viz/pitching.py`
- Create: `viz/tests/test_pitching_viz.py`

**Interfaces:**
- Consumes: `viz.theme.*`, dict de `core.pitching.movement_points`
- Produces: `viz.pitching.movement_bubble(points: dict, name: str, show_individual: bool=True) -> go.Figure`

- [ ] **Step 1: Escribir el test primero**

```python
import plotly.graph_objects as go
import pandas as pd
from core.pitching import movement_points
from viz import pitching as vp

def _pts():
    df = pd.DataFrame({
        "TaggedPitchType": ["Slider", "Slider", "Fastball", "Fastball"],
        "PitchCall": ["StrikeSwinging", "FoulBall", "InPlay", "StrikeCalled"],
        "RelSpeed": [84, 85, 94, 95], "SpinRate": [2400, 2410, 2200, 2210],
        "HorzBreak": [6, 7, -8, -9], "InducedVertBreak": [2, 3, 16, 17],
    })
    return movement_points(df)

def test_movement_bubble_returns_figure():
    fig = vp.movement_bubble(_pts(), "Test Pitcher")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0

def test_movement_bubble_empty():
    fig = vp.movement_bubble({"pitches": [], "centroids": []}, "X")
    assert isinstance(fig, go.Figure)
```

- [ ] **Step 2: Correr el test — debe fallar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_pitching_viz.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'viz.pitching'`.

- [ ] **Step 3: Crear `viz/pitching.py` con `movement_bubble` (y el helper `_f`)**

```python
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
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_pitching_viz.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add viz/pitching.py viz/tests/test_pitching_viz.py
git commit -m "feat: viz/pitching movement_bubble (Panel de Arsenal interactivo)"
```

---

### Task 5: `viz/pitching.py` — location_scatter, hot_zone, location_by_pitch

**Files:**
- Modify: `viz/pitching.py` (añadir 3 funciones)
- Modify: `viz/tests/test_pitching_viz.py` (añadir smoke tests)

**Interfaces:**
- Produces: `location_scatter(df, name)->go.Figure`, `hot_zone(df, name)->go.Figure`,
  `location_by_pitch(df, name, max_types=6)->go.Figure`

- [ ] **Step 1: Añadir los smoke tests primero**

```python
def _loc_df():
    return pd.DataFrame({
        "TaggedPitchType": ["Slider"] * 6 + ["Fastball"] * 6,
        "PlateLocSide": [0.1, -0.2, 0.3, 0.0, 0.5, -0.1, 0.2, -0.3, 0.1, 0.0, 0.4, -0.2],
        "PlateLocHeight": [2.5, 2.4, 2.6, 2.1, 3.0, 2.2, 2.5, 2.7, 2.3, 2.9, 2.4, 2.6],
        "RelSpeed": [84, 85, 84, 86, 83, 85, 94, 95, 93, 96, 94, 95],
    })

def test_location_scatter_ok_and_empty():
    assert isinstance(vp.location_scatter(_loc_df(), "P"), go.Figure)
    assert isinstance(vp.location_scatter(pd.DataFrame(), "P"), go.Figure)

def test_hot_zone_ok_and_sparse():
    assert isinstance(vp.hot_zone(_loc_df(), "P"), go.Figure)
    assert isinstance(vp.hot_zone(_loc_df().head(3), "P"), go.Figure)

def test_location_by_pitch_ok_and_empty():
    assert isinstance(vp.location_by_pitch(_loc_df(), "P"), go.Figure)
    assert isinstance(vp.location_by_pitch(pd.DataFrame(), "P"), go.Figure)
```

- [ ] **Step 2: Correr — deben fallar (funciones inexistentes)**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_pitching_viz.py -k "location or hot_zone" -v`
Expected: FAIL con `AttributeError: module 'viz.pitching' has no attribute 'location_scatter'`.

- [ ] **Step 3: Añadir las 3 funciones a `viz/pitching.py`**

```python
def location_scatter(df, name):
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns):
        return theme.empty_fig("No location data")
    loc = df.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    if loc.empty:
        return theme.empty_fig("No location data")
    types = list(loc["TaggedPitchType"].dropna().unique())
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
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(df.columns):
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
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_pitching_viz.py -v`
Expected: todos pasan (movement_bubble + location*).

- [ ] **Step 5: Commit**

```bash
git add viz/pitching.py viz/tests/test_pitching_viz.py
git commit -m "feat: viz/pitching location_scatter, hot_zone, location_by_pitch (Plotly)"
```

---

### Task 6: `viz/pitching.py` — velo_trend, usage_heatmap

**Files:**
- Modify: `viz/pitching.py` (añadir 2 funciones)
- Modify: `viz/tests/test_pitching_viz.py` (añadir smoke tests)

**Interfaces:**
- Consumes: tabla de `core.pitching.build_usage_by_count` para `usage_heatmap`
- Produces: `velo_trend(df, name)->go.Figure`, `usage_heatmap(tab: pd.DataFrame, name)->go.Figure`

- [ ] **Step 1: Añadir los smoke tests primero**

```python
from core.pitching import build_usage_by_count

def test_velo_trend_ok_and_empty():
    df = pd.DataFrame({
        "TaggedPitchType": ["Slider", "Slider", "Fastball"],
        "RelSpeed": [84, 85, 94],
        "Date": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-01"]),
    })
    assert isinstance(vp.velo_trend(df, "P"), go.Figure)
    assert isinstance(vp.velo_trend(pd.DataFrame(), "P"), go.Figure)

def test_usage_heatmap_ok_and_empty():
    df = pd.DataFrame({"TaggedPitchType": ["Slider", "Fastball", "Slider"],
                       "Count": ["0-0", "0-0", "1-1"]})
    tab = build_usage_by_count(df)
    assert isinstance(vp.usage_heatmap(tab, "P"), go.Figure)
    assert isinstance(vp.usage_heatmap(pd.DataFrame(), "P"), go.Figure)
```

- [ ] **Step 2: Correr — deben fallar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_pitching_viz.py -k "velo or usage" -v`
Expected: FAIL con `AttributeError: ... has no attribute 'velo_trend'`.

- [ ] **Step 3: Añadir las 2 funciones a `viz/pitching.py`**

```python
def velo_trend(df, name):
    if "RelSpeed" not in df.columns or "Date" not in df.columns:
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
```

- [ ] **Step 4: Correr los tests — todos pasan**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/ -v`
Expected: todos los smoke tests de viz pasan.

- [ ] **Step 5: Commit**

```bash
git add viz/pitching.py viz/tests/test_pitching_viz.py
git commit -m "feat: viz/pitching velo_trend y usage_heatmap (Plotly)"
```

---

### Task 7: `viz/export.py` — Plotly → PNG para el PDF (con degradación) + kaleido

**Files:**
- Create: `viz/export.py`
- Create: `viz/tests/test_export.py`
- Modify: `trackman_app.py` (`_fig_to_img` acepta figuras Plotly)
- Modify: `requirements.txt` (añadir `kaleido`)

**Interfaces:**
- Produces: `viz.export.plotly_png_array(fig, scale=2) -> np.ndarray | None`

- [ ] **Step 1: Escribir el test primero — `viz/tests/test_export.py`**

```python
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
```

- [ ] **Step 2: Correr — debe fallar (módulo inexistente)**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_export.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'viz.export'`.

- [ ] **Step 3: Crear `viz/export.py`**

```python
"""Plotly → PNG para el reporte PDF, con degradación elegante si falta kaleido."""
import io

def plotly_png_array(fig, scale=2):
    """Devuelve un array RGBA (para imshow de matplotlib) o None si kaleido no está / falla."""
    try:
        import matplotlib.image as mpimg
        png = fig.to_image(format="png", scale=scale)  # requiere kaleido
        return mpimg.imread(io.BytesIO(png))
    except Exception:
        return None
```

- [ ] **Step 4: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest viz/tests/test_export.py -v`
Expected: 2 passed.

- [ ] **Step 5: Modificar `_fig_to_img` en `trackman_app.py` para aceptar figuras Plotly**

Reemplazar la función `_fig_to_img` (actualmente en `trackman_app.py`) por:

```python
def _fig_to_img(src_fig):
    import matplotlib.image as mpimg
    # Figura Plotly → ruta por kaleido (viz.export). Si falla, se propaga la excepción
    # y el llamador (_pdf_two_charts/_pdf_single_chart) dibuja "Chart unavailable".
    try:
        import plotly.graph_objects as _go
        if isinstance(src_fig, _go.Figure):
            from viz.export import plotly_png_array
            arr = plotly_png_array(src_fig)
            if arr is None:
                raise RuntimeError("kaleido no disponible")
            return arr
    except ImportError:
        pass
    img_buf = io.BytesIO()
    src_fig.savefig(img_buf, format="png", dpi=150,
                    bbox_inches="tight", facecolor=src_fig.get_facecolor())
    img_buf.seek(0)
    return mpimg.imread(img_buf)
```

- [ ] **Step 6: Añadir `kaleido` a `requirements.txt`**

Añadir una línea `kaleido` al final de `requirements.txt`.

- [ ] **Step 7: Verificar sintaxis y tests globales**

Run: `cd /Users/joseramirez/trackman-analayzer && python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: "ok" y todo pasa.

- [ ] **Step 8: Commit**

```bash
git add viz/export.py viz/tests/test_export.py trackman_app.py requirements.txt
git commit -m "feat: PDF export vía Plotly+kaleido con degradación elegante"
```

---

### Task 8: Rewire `render_pitching` — Plotly end-to-end + Panel de Arsenal en Summary

**Files:**
- Modify: `trackman_app.py` (`render_pitching`, ~línea 1804)

**Interfaces:**
- Consumes: `core.pitching.{arsenal_stuff, movement_points, build_usage_by_count}` (alias
  `build_pitch_summary`, `compute_pitch_discipline` ya importados), `viz.pitching.*`
- Produces: nada nuevo (UI). `export_pitching_pdf` conserva su firma `(pitcher, summary_df,
  disc_df, fig_loc, fig_kde, fig_vel, fig_mov, date_range)` — ahora recibe figuras Plotly.

- [ ] **Step 1: Añadir el import de viz al bloque de imports de `trackman_app.py`**

```python
from viz import pitching as vpitch
```

- [ ] **Step 2: Reemplazar la función `render_pitching` completa por la versión con Plotly + Arsenal**

```python
def render_pitching(df, master_df, lmeta):
    st.markdown('<div class="sh">⚾ Pitching Dashboard</div>', unsafe_allow_html=True)
    st.info(f"📋 **{lmeta['label']} benchmarks** · "
            f"Elite velo: {lmeta['velo_elite']}+ mph · Avg: {lmeta['velo_avg']} mph · "
            f"{lmeta['context']}")
    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No 'Pitcher' column."); return
    pitchers = sorted(df["Pitcher"].dropna().unique())
    selected = player_search_select(pitchers, "Select Pitcher", "pitcher")
    pf = df[df["Pitcher"] == selected].copy(); n = len(pf)
    if n < 15:
        st.warning(f"⚠️ **{selected}** — only **{n}** pitches (min: 15).")
    avg_v = pf["RelSpeed"].mean() if "RelSpeed" in pf.columns else np.nan
    max_v = pf["RelSpeed"].max() if "RelSpeed" in pf.columns else np.nan
    avg_sp = pf["SpinRate"].mean() if "SpinRate" in pf.columns else np.nan
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Pitches", f"{n:,}")
    with c2: st.metric("Avg Velo", fmt(avg_v, " mph"),
                       delta=f"Max {max_v:.1f}" if not np.isnan(max_v) else None)
    with c3: st.metric("Avg Spin", fmt(avg_sp, " rpm", 0))
    with c4: st.metric("Pitches Types", str(pf["TaggedPitchType"].nunique()))
    with c5: st.metric("Distinct Dates",
                       str(pf["Date"].dt.date.nunique()) if "Date" in pf.columns else "—")
    st.markdown("<br>", unsafe_allow_html=True)
    render_percentile_section(
        selected, league_pitcher_table(df), PITCHER_INVERT,
        defaults={"Avg Velo": float(lmeta.get("velo_avg", 88)),
                  "Max Velo": float(lmeta.get("velo_elite", 93)),
                  "Avg Spin": 2200.0, "Zone %": 48.0, "Whiff %": 24.0,
                  "Chase %": 28.0, "K %": 22.0, "BB %": 8.5},
        key="pit")

    # Figuras Plotly (una sola fuente; también alimentan el PDF)
    fig_mov = vpitch.movement_bubble(movement_points(pf), selected,
                                     show_individual=st.session_state.get("arsenal_show_ind", True))
    fig_loc = vpitch.location_scatter(pf, selected)
    fig_kde = vpitch.hot_zone(pf, selected)
    fig_vel = vpitch.velo_trend(pf, selected)

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Summary", "📍 Location", "📊 Trends", "🏟️ Stadium"])
    with tab1:
        st.markdown('<div class="sh">🎯 Arsenal — Stuff</div>', unsafe_allow_html=True)
        st.checkbox("Mostrar pitcheos individuales", value=True, key="arsenal_show_ind")
        st.plotly_chart(fig_mov, use_container_width=True)
        summary_df = arsenal_stuff(pf)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        csv_dl(summary_df, f"{selected}_arsenal.csv")
        st.markdown('<div class="sh">Discipline</div>', unsafe_allow_html=True)
        disc_df = compute_pitch_discipline(pf)
        if disc_df.empty:
            st.info("PitchCall column required.")
        else:
            st.dataframe(disc_df, use_container_width=True, hide_index=True)
            csv_dl(disc_df, f"{selected}_discipline.csv")
    with tab2:
        cl, cr = st.columns(2)
        with cl: st.plotly_chart(fig_loc, use_container_width=True)
        with cr: st.plotly_chart(fig_kde, use_container_width=True)
        st.markdown('<div class="sh">Location by Pitch Type</div>', unsafe_allow_html=True)
        st.plotly_chart(vpitch.location_by_pitch(pf, selected), use_container_width=True)
    with tab3:
        st.plotly_chart(fig_vel, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.plotly_chart(vpitch.usage_heatmap(build_usage_by_count(pf), selected),
                        use_container_width=True)
    with tab4:
        st.info("Stadium analysis coming soon.")
    st.markdown('<div class="sh">📤 Export</div>', unsafe_allow_html=True)
    dr = (f"{df['Date'].min().date()}→{df['Date'].max().date()}"
          if df["Date"].notna().any() else "All dates")
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("📄 Build PDF Report", key="btn_pdf_pitch"):
            with st.spinner("Building PDF…"):
                pdf_b = export_pitching_pdf(selected, summary_df,
                                            disc_df if not disc_df.empty else pd.DataFrame(),
                                            fig_loc, fig_kde, fig_vel, fig_mov, dr)
            st.download_button("⬇️ Download PDF", pdf_b, f"{selected}_pitching.pdf",
                               "application/pdf", key="dl_pdf_pitch")
    with ec2:
        csv_dl(pf, f"{selected}_raw.csv", "⬇️ Raw CSV")
```

Nota: se eliminó la línea final `for f in [...]: plt.close(f)` (las figuras Plotly no se cierran con matplotlib). El `summary_df` del PDF ahora es `arsenal_stuff` (incluye CSW%).

- [ ] **Step 3: Verificar sintaxis**

Run: `cd /Users/joseramirez/trackman-analayzer && python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')"`
Expected: "ok".

- [ ] **Step 4: Verificación manual end-to-end (skill `verify` / `run`)**

Arrancar el app y ejercitar el modo Pitching con datos de prueba:

```bash
cd /Users/joseramirez/trackman-analayzer && streamlit run trackman_app.py
```

Checklist manual (fuente ⬆️ Upload CSVs con un CSV de TrackMan):
- Summary muestra el bubble de movimiento interactivo (hover con velo/spin/whiff/CSW) + tabla con columna **CSW %**.
- El checkbox "Mostrar pitcheos individuales" activa/desactiva el scatter de fondo.
- Location: scatter + hot zone + subplots por tipo, todos con hover/zoom.
- Trends: velo_trend y usage_heatmap interactivos.
- "Build PDF Report" genera un PDF (con gráficos si kaleido está; con nota "Chart unavailable" si no) sin romper.

- [ ] **Step 5: Commit**

```bash
git add trackman_app.py
git commit -m "feat: render_pitching en Plotly + Panel de Arsenal Stuff en Summary"
```

---

### Task 9: Regresión completa, limpieza de código muerto y docs

**Files:**
- Modify: `trackman_app.py` (borrar plot functions de pitching ya sin uso — con grep de verificación)
- Modify: `README.md` (changelog)

**Interfaces:** ninguna nueva.

- [ ] **Step 1: Verificar que las plot functions de pitching ya no se usan en ningún lado**

Run: `cd /Users/joseramirez/trackman-analayzer && grep -nE "plot_pitch_locations|plot_hot_zone|plot_location_by_pitch|plot_velocity_tendency|plot_usage_by_count|plot_movement_profile" trackman_app.py`
Expected: solo aparecen sus propias definiciones (no hay llamadas fuera de ellas). Si alguna
tiene otra llamada (p.ej. un helper compartido usado por hitting), **NO** la borres.

- [ ] **Step 2: Borrar las definiciones de las plot functions confirmadas sin uso**

Borrar de `trackman_app.py` las defs de: `plot_pitch_locations`, `plot_hot_zone`,
`plot_location_by_pitch`, `plot_velocity_tendency`, `plot_usage_by_count`, `plot_movement_profile`.
Conservar los helpers compartidos (`zone_heatmap_ax`, `draw_savant_zone`, `draw_plate`,
`style_zone_ax`, `setup_savant_fig`) — los usa el modo Hitting.

- [ ] **Step 3: Verificar sintaxis y que el resto del app siga íntegro**

Run: `cd /Users/joseramirez/trackman-analayzer && python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && grep -nE "plot_spray_chart|plot_damage_zone|zone_heatmap_ax" trackman_app.py | head`
Expected: "ok" y los helpers de hitting siguen presentes.

- [ ] **Step 4: Correr toda la suite de tests**

Run: `cd /Users/joseramirez/trackman-analayzer && python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: todo pasa.

- [ ] **Step 5: Verificación manual de no-regresión en los otros modos**

Arrancar el app y confirmar que Hitting, League, Top Plays y Trayectorias 3D siguen funcionando
(cargan y renderizan sin excepción).

```bash
cd /Users/joseramirez/trackman-analayzer && streamlit run trackman_app.py
```

- [ ] **Step 6: Actualizar `README.md` con el changelog de esta iteración**

Añadir bajo la lista de changelogs:

```markdown
## Changelog v4.9

- 🧱 Refactor "híbrido por fases": analítica de Pitching extraída a paquetes limpios
  `core/` (métricas puras) y `viz/` (figuras Plotly) — deja el terreno listo para un
  frontend futuro sin reescribir lógica.
- 🎯 Modo **Pitching interactivo**: los 6 gráficos migrados a Plotly (hover, zoom).
- 🆕 **Panel de Arsenal "Stuff"** en Summary: plot de movimiento interactivo (burbuja por
  tipo, tamaño = uso, hover con velo/spin/whiff/CSW) + tabla de arsenal con **CSW%**.
- 🖨️ PDF de pitching unificado sobre Plotly (vía `kaleido`, con degradación elegante).
- Nueva dependencia: `kaleido`.
```

- [ ] **Step 7: Commit**

```bash
git add trackman_app.py README.md
git commit -m "chore: limpiar plot functions de pitching sin uso + changelog v4.9"
```

- [ ] **Step 8: Abrir el Pull Request**

(Requiere `gh auth login` hecho por el usuario una vez.)

```bash
cd /Users/joseramirez/trackman-analayzer && git push -u origin iter1-pitching-interactive-arsenal
gh pr create --title "Iter 1: Pitching interactivo + Panel de Arsenal Stuff" \
  --body "Extrae analítica de Pitching a core/ + viz/, migra los 6 gráficos a Plotly interactivo, y agrega el Panel de Arsenal Stuff (con CSW%). Ver docs/superpowers/plans/2026-07-15-pitching-interactive-arsenal.md"
```

---

## Self-Review

**1. Spec coverage:**
- Paquetes `core/`+`viz/` sin Streamlit/matplotlib → Task 1, 2, 3. ✓
- 6 gráficos → Plotly → Tasks 4, 5, 6 (movement/location/hot_zone/by_pitch/velo/usage). ✓
- Panel de Arsenal "Stuff" (plot + tabla + CSW%) → Task 2 (datos) + Task 4 (plot) + Task 8 (UI en Summary). ✓
- CSW% definición → Task 2 (`_csw_pct`), test explícito. ✓
- Mover primitivos compartidos sin duplicar → Task 1, con import en el monolito. ✓
- PDF unificado vía kaleido + degradación → Task 7. ✓
- `render_pitching` delgado + movimiento sale de Trends a Summary → Task 8. ✓
- Manejo de errores (estado vacío por builder) → `empty_fig` en Task 3, usado en 4/5/6. ✓
- Tests incl. regresión → Task 1, 2 (regresión), smoke en 4/5/6/7. ✓
- No-goals respetados (sin zona/tunneling/otros modos/React). ✓

**2. Placeholder scan:** Sin TBD/TODO. Todo el código nuevo está completo; los movimientos muestran el body verbatim. ✓

**3. Type consistency:** `arsenal_stuff`/`movement_points`/`pitch_summary`/`pitch_discipline`/`build_usage_by_count` definidos en Task 2 y consumidos con esas firmas en Tasks 4/6/8. `theme.empty_fig/color_map/strike_zone_shapes/base_layout/movement_rings` definidos en Task 3, usados en 4/5/6. `export_pitching_pdf` conserva firma. `_fig_to_img` polimórfico. ✓

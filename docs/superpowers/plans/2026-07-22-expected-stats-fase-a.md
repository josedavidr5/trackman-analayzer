# Stats Esperados — Fase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development o superpowers:executing-plans. Steps con checkbox (`- [ ]`). La Task 6 (captura Playwright) requiere ver imágenes — trabajo de controller.

**Goal:** Agregar la capa evaluativa: modelo híbrido EV×ángulo → xwOBA/xBA/xSLG en `core/expected.py`, cableado en Hitting, Pitching y League.

**Architecture:** Nuevo módulo puro `core/expected.py` (modelo paramétrico base MLB + recalibración empírica por shrinkage) que reusa `WOBA_W`, `count_pa`, `batted_ball_mask`, `compute_woba` de `core/metrics.py`. Wiring en `trackman_app.py` con `viz_card`.

**Tech Stack:** numpy, pandas, pytest, Streamlit, Playwright (verificación).

## Global Constraints

- Módulo `core/expected.py` **puro**: sin Streamlit ni matplotlib.
- Reusar constantes/funciones existentes de `core.metrics`: `WOBA_W`, `count_pa`, `batted_ball_mask`, `compute_woba`. NO redefinir pesos wOBA.
- `trackman_app.py` usa **CRLF** — al editar por script preservar `\r\n` (aquí se edita con Edit, que lo respeta).
- Solo esta fase: expected stats. **Run value NO** (es Fase B).
- Anclas xwOBA-on-contact (son los tests): barrel(100,28) ≥0.85 · línea(95,15)∈[0.57,0.73] · promedio(89,12)∈[0.29,0.45] · débil(70,-5) ≤0.20 · popup(80,50) ≤0.10.
- Recalibración activa cuando ≥500 batazos (`RECAL_MIN_BB=500`); pseudo-conteo shrinkage `SHRINK_K=50`.
- Verificación final: suite verde + `import trackman_app` OK + captura Playwright con sign-off.

---

### Task 1: `core/expected.py` — modelo base MLB + `xwoba_contact`

**Files:**
- Create: `core/expected.py`
- Test: `core/tests/test_expected.py`

**Interfaces:**
- Produces: `base_outcome_probs(ev, la) -> np.ndarray[5]` (orden `[out,1B,2B,3B,HR]`, suma 1, ≥0); `xwoba_contact(ev, la, grid=None) -> float`; constantes `OUTCOMES`, `_OUT_W`, `_SLG_W`.

- [ ] **Step 1: Escribir los tests de anclas/validez/monotonía**

```python
# core/tests/test_expected.py
import numpy as np
import pandas as pd
import pytest
from core import expected as ex


@pytest.mark.parametrize("ev,la,lo,hi", [
    (100, 28, 0.85, 3.0),    # barrel: piso alto
    (95, 15, 0.57, 0.73),    # línea dura
    (89, 12, 0.29, 0.45),    # contacto promedio
    (70, -5, 0.0, 0.20),     # roletazo débil
    (80, 50, 0.0, 0.10),     # popup
])
def test_anchors(ev, la, lo, hi):
    assert lo <= ex.xwoba_contact(ev, la) <= hi


def test_probs_valid_over_grid():
    for ev in range(40, 121, 5):
        for la in range(-40, 61, 5):
            p = ex.base_outcome_probs(ev, la)
            assert p.shape == (5,)
            assert (p >= -1e-9).all()
            assert abs(p.sum() - 1.0) < 1e-6


def test_monotonic_ev_in_line_band():
    xs = [ex.xwoba_contact(ev, 18) for ev in (80, 90, 100, 108)]
    assert xs == sorted(xs)


def test_popup_worse_than_line_same_ev():
    assert ex.xwoba_contact(95, 50) < ex.xwoba_contact(95, 15)
```

- [ ] **Step 2: Correr los tests → fallan (ModuleNotFoundError)**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: FAIL (no module `core.expected`).

- [ ] **Step 3: Implementar el modelo base**

```python
# core/expected.py
"""Capa evaluativa: modelo híbrido EV×ángulo y stats esperados (xwOBA/xBA/xSLG). Puro."""
import numpy as np
import pandas as pd
from core.metrics import WOBA_W, count_pa, batted_ball_mask, compute_woba

OUTCOMES = ["out", "1B", "2B", "3B", "HR"]
_OUT_W = np.array([0.0, WOBA_W["1B"], WOBA_W["2B"], WOBA_W["3B"], WOBA_W["HR"]])
_SLG_W = np.array([0.0, 1.0, 2.0, 3.0, 4.0])

RECAL_MIN_BB = 500
SHRINK_K = 50.0
EV_BIN, LA_BIN = 5.0, 5.0
EV_LO, EV_HI = 40.0, 120.0
LA_LO, LA_HI = -40.0, 60.0


def _logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def base_outcome_probs(ev, la):
    """Vector [out,1B,2B,3B,HR] de la base MLB paramétrica para un batazo (ev,la)."""
    ev = float(ev); la = float(la)
    p_hr = 0.92 * _logistic((ev - 99.0) / 3.0) * np.exp(-((la - 27.0) / 9.0) ** 2)
    hit = 0.58 * np.exp(-((la - 16.0) / 14.0) ** 2) * _logistic((ev - 82.0) / 8.0)
    hit = float(np.clip(hit, 0.0, 0.95))
    d_share = 0.15 + 0.45 * _logistic((ev - 88.0) / 6.0) * np.exp(-((la - 20.0) / 12.0) ** 2)
    t_share = 0.03
    p_2b = hit * d_share
    p_3b = hit * t_share
    p_1b = hit - p_2b - p_3b
    p = np.clip(np.array([0.0, p_1b, p_2b, p_3b, p_hr], dtype=float), 0.0, None)
    s = p[1:].sum()
    if s > 1.0:
        p[1:] = p[1:] / s
        s = 1.0
    p[0] = 1.0 - s
    return p


def xwoba_contact(ev, la, grid=None):
    if ev is None or la is None or pd.isna(ev) or pd.isna(la):
        return np.nan
    p = hybrid_outcome_probs(ev, la, grid) if grid else base_outcome_probs(ev, la)
    return float(p @ _OUT_W)
```

(Nota: `xwoba_contact` referencia `hybrid_outcome_probs`, que se define en la Task 3; en la Task 1 solo se ejercita la rama `grid=None`, así que las llamadas de test no tocan `hybrid_outcome_probs`.)

- [ ] **Step 4: Correr los tests → pasan (ajustar constantes si alguna ancla falla por poco)**

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: PASS (5 anclas + validez + monotonía). Si `línea dura` o `promedio` caen fuera por poco, ajustar el escalar `0.58` de `hit` y/o los centros, y re-correr.

- [ ] **Step 5: Commit**

```bash
git add core/expected.py core/tests/test_expected.py
git commit -m "feat(expected): modelo base MLB EV×ángulo + xwoba_contact"
```

---

### Task 2: Expected por batazo y por PA

**Files:**
- Modify: `core/expected.py`
- Test: `core/tests/test_expected.py`

**Interfaces:**
- Produces: `expected_batted_balls(df, grid=None) -> DataFrame[xwoba,xba,xslg]`; `xwoba_pa(df, grid=None) -> float`; `expected_summary(df, grid=None) -> dict`.

- [ ] **Step 1: Escribir los tests**

```python
def _bb_df():
    # 3 batazos (2 buenos, 1 débil) + 1 K + 1 BB → PA=5
    return pd.DataFrame({
        "PitchCall": ["InPlay", "InPlay", "InPlay", "StrikeSwinging", "BallCalled"],
        "PlayResult": ["2B", "Out", "Out", "K", "BB"],
        "ExitSpeed": [100.0, 95.0, 70.0, np.nan, np.nan],
        "Angle":     [28.0, 15.0, -5.0, np.nan, np.nan],
    })


def test_expected_batted_balls_shape():
    xbb = ex.expected_batted_balls(_bb_df())
    assert list(xbb.columns) == ["xwoba", "xba", "xslg"]
    assert len(xbb) == 3
    assert (xbb["xba"].between(0, 1)).all()


def test_xwoba_pa_uses_expected_plus_actual_bb():
    df = _bb_df()
    xw = ex.xwoba_pa(df)
    # denom = PA(5) - SacBunt(0) = 5 ; num = Σxwoba(3 batazos) + WOBA_W['BB']
    xbb = ex.expected_batted_balls(df)
    expected = round((xbb["xwoba"].sum() + ex.WOBA_W["BB"]) / 5, 3)
    assert xw == expected


def test_xwoba_pa_nan_without_pa():
    assert pd.isna(ex.xwoba_pa(pd.DataFrame({"ExitSpeed": [], "Angle": []})))


def test_expected_summary_keys():
    s = ex.expected_summary(_bb_df())
    assert set(s) >= {"xwoba", "xba", "xslg", "woba", "woba_minus_xwoba", "n_bip"}
    assert s["n_bip"] == 3
```

- [ ] **Step 2: Correr → fallan** (`AttributeError: expected_batted_balls`)

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
def expected_batted_balls(df, grid=None):
    """xwoba/xba/xslg por batazo (filas InPlay con EV+ángulo)."""
    cols = ["xwoba", "xba", "xslg"]
    if not {"ExitSpeed", "Angle"}.issubset(df.columns):
        return pd.DataFrame(columns=cols)
    bip = batted_ball_mask(df)
    sub = df.loc[bip, ["ExitSpeed", "Angle"]].dropna()
    rows = []
    for ev, la in zip(sub["ExitSpeed"], sub["Angle"]):
        p = hybrid_outcome_probs(ev, la, grid) if grid else base_outcome_probs(ev, la)
        rows.append((float(p @ _OUT_W), float(p[1:].sum()), float(p @ _SLG_W)))
    return pd.DataFrame(rows, columns=cols, index=sub.index)


def xwoba_pa(df, grid=None):
    """xwOBA por PA: batazos esperados + K/BB/HBP reales; espeja compute_woba."""
    pa = count_pa(df)
    if pa == 0:
        return np.nan
    xbb = expected_batted_balls(df, grid)
    num = float(xbb["xwoba"].sum()) if not xbb.empty else 0.0
    if "PlayResult" in df.columns:
        pr = df["PlayResult"].astype(str)
        for res in ("BB", "HBP"):
            num += WOBA_W[res] * int(pr.eq(res).sum())
        denom = pa - int(pr.eq("SacBunt").sum())
    else:
        denom = pa
    return round(num / denom, 3) if denom > 0 else np.nan


def expected_summary(df, grid=None):
    xbb = expected_batted_balls(df, grid)
    woba = compute_woba(df)
    xw = xwoba_pa(df, grid)
    n_bip = int(len(xbb))
    return {
        "xwoba": float(xw) if pd.notna(xw) else None,
        "xba": float(xbb["xba"].mean()) if n_bip else None,
        "xslg": float(xbb["xslg"].mean()) if n_bip else None,
        "woba": float(woba) if pd.notna(woba) else None,
        "woba_minus_xwoba": (float(woba) - float(xw)) if pd.notna(woba) and pd.notna(xw) else None,
        "n_bip": n_bip,
    }
```

- [ ] **Step 4: Correr → pasan**

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/expected.py core/tests/test_expected.py
git commit -m "feat(expected): xwoba/xba/xslg por batazo y por PA + summary"
```

---

### Task 3: Grid empírico + shrinkage híbrido

**Files:**
- Modify: `core/expected.py`
- Test: `core/tests/test_expected.py`

**Interfaces:**
- Produces: `empirical_grid(df) -> {"cells": dict, "n": int, "recalibrated": bool}`; `hybrid_outcome_probs(ev, la, grid) -> np.ndarray[5]`.

- [ ] **Step 1: Escribir los tests**

```python
def test_hybrid_n0_equals_base():
    empty = {"cells": {}, "n": 0, "recalibrated": False}
    p = ex.hybrid_outcome_probs(95, 15, empty)
    assert np.allclose(p, ex.base_outcome_probs(95, 15))


def test_hybrid_large_n_tends_empirical():
    # celda EV~95/LA~15 con 5000 batazos, todos HR
    df = pd.DataFrame({
        "PitchCall": ["InPlay"] * 5000,
        "PlayResult": ["HR"] * 5000,
        "ExitSpeed": [95.0] * 5000,
        "Angle": [15.0] * 5000,
    })
    grid = ex.empirical_grid(df)
    assert grid["recalibrated"] is True
    p = ex.hybrid_outcome_probs(95, 15, grid)
    assert p[4] > 0.9   # domina el empírico (HR)


def test_empirical_grid_below_threshold_not_recalibrated():
    df = pd.DataFrame({
        "PitchCall": ["InPlay"] * 10, "PlayResult": ["1B"] * 10,
        "ExitSpeed": [90.0] * 10, "Angle": [12.0] * 10,
    })
    assert ex.empirical_grid(df)["recalibrated"] is False
```

- [ ] **Step 2: Correr → fallan**

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: FAIL (`empirical_grid`/`hybrid_outcome_probs` no existen).

- [ ] **Step 3: Implementar**

```python
_BIP_CLASS = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}   # otros BIP → 0 (out)


def _bin_idx(ev, la):
    ei = int(np.clip((float(ev) - EV_LO) // EV_BIN, 0, (EV_HI - EV_LO) / EV_BIN - 1))
    li = int(np.clip((float(la) - LA_LO) // LA_BIN, 0, (LA_HI - LA_LO) / LA_BIN - 1))
    return ei, li


def empirical_grid(df):
    """{(ei,li): (counts[5], n)} desde los batazos del dataset + total y flag."""
    cells = {}
    total = 0
    if not {"ExitSpeed", "Angle", "PlayResult"}.issubset(df.columns):
        return {"cells": cells, "n": 0, "recalibrated": False}
    bip = batted_ball_mask(df)
    sub = df.loc[bip, ["ExitSpeed", "Angle", "PlayResult"]].dropna(subset=["ExitSpeed", "Angle"])
    for ev, la, res in zip(sub["ExitSpeed"], sub["Angle"], sub["PlayResult"].astype(str)):
        key = _bin_idx(ev, la)
        c, n = cells.get(key, (np.zeros(5), 0))
        c = c.copy(); c[_BIP_CLASS.get(res, 0)] += 1
        cells[key] = (c, n + 1)
        total += 1
    return {"cells": cells, "n": total, "recalibrated": total >= RECAL_MIN_BB}


def hybrid_outcome_probs(ev, la, grid):
    base = base_outcome_probs(ev, la)
    if not grid or not grid.get("cells"):
        return base
    c, n = grid["cells"].get(_bin_idx(ev, la), (np.zeros(5), 0))
    if n == 0:
        return base
    p_emp = c / n
    return (n * p_emp + SHRINK_K * base) / (n + SHRINK_K)
```

- [ ] **Step 4: Correr toda la suite del módulo → pasa**

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add core/expected.py core/tests/test_expected.py
git commit -m "feat(expected): grid empírico + shrinkage híbrido MLB/liga"
```

---

### Task 4: Wiring en Hitting — tarjeta VALOR ESPERADO

**Files:**
- Modify: `trackman_app.py` (imports, helper cacheado, `render_hitting`)

- [ ] **Step 1: Importar el módulo y agregar helper cacheado**

Agregar junto a los otros imports `from core...` (después de la línea `from core.hitting import (...)`):
```python
from core.expected import empirical_grid, expected_summary, xwoba_pa, xwoba_against_by_pitch
```

Y agregar el helper cacheado justo antes de `def render_pitching(` (línea ~1302):
```python
@st.cache_data(show_spinner=False)
def get_expected_grid(_df, cache_key):
    return empirical_grid(_df)


def _xgrid_note(xgrid):
    return (f"Modelo recalibrado con tu liga · {xgrid['n']} batazos"
            if xgrid.get("recalibrated")
            else f"Modelo base MLB · tu liga: {xgrid['n']} batazos (≥500 para recalibrar)")


def _grid_key(master):
    return (len(master), round(float(master["ExitSpeed"].sum()), 1)
            if "ExitSpeed" in master.columns and master["ExitSpeed"].notna().any() else 0)
```

- [ ] **Step 2: Agregar la tarjeta VALOR ESPERADO en `render_hitting`**

Insertar justo después del bloque de métricas de cabecera (después de `st.markdown("<br>",unsafe_allow_html=True)` de la línea ~1438, antes del `if disc:`):
```python
    xgrid = get_expected_grid(master_df, _grid_key(master_df))
    esum = expected_summary(bdf, xgrid)
    with viz_card("VALOR ESPERADO", "xwOBA / xBA / xSLG",
                  "Calidad de contacto esperada (EV+ángulo) vs resultado real — quita suerte y defensa."):
        e1, e2, e3, e4 = st.columns(4)
        with e1: st.metric("xwOBA", fmt(esum["xwoba"], "", 3))
        with e2: st.metric("xBA", fmt(esum["xba"], "", 3))
        with e3: st.metric("xSLG", fmt(esum["xslg"], "", 3))
        with e4:
            d = esum["woba_minus_xwoba"]
            st.metric("wOBA − xwOBA", fmt(d, "", 3),
                      delta=("sobre-rinde" if d and d > 0 else "sub-rinde" if d else None),
                      delta_color="off")
        st.caption(_xgrid_note(xgrid))
    st.markdown("<br>", unsafe_allow_html=True)
```

- [ ] **Step 3: Verificar sintaxis + import + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: ok, import ok, todos pasan (70 + nuevos de expected).

- [ ] **Step 4: Commit**

```bash
git add trackman_app.py
git commit -m "feat: tarjeta VALOR ESPERADO (xwOBA/xBA/xSLG) en Hitting"
```

---

### Task 5: Wiring en Pitching (xwOBA-contra) y League (fila xwOBA)

**Files:**
- Modify: `core/expected.py` (agregar `xwoba_against_by_pitch`), `core/tests/test_expected.py`, `trackman_app.py`

**Interfaces:**
- Produces: `xwoba_against_by_pitch(df, grid=None) -> DataFrame[Pitch,xwOBAcon,BBE]`.

- [ ] **Step 1: Test de `xwoba_against_by_pitch`**

```python
def test_xwoba_against_by_pitch():
    df = pd.DataFrame({
        "TaggedPitchType": ["Slider", "Slider", "Fastball"],
        "PitchCall": ["InPlay", "InPlay", "InPlay"],
        "PlayResult": ["Out", "Out", "HR"],
        "ExitSpeed": [70.0, 72.0, 104.0],
        "Angle": [-5.0, 2.0, 27.0],
    })
    t = ex.xwoba_against_by_pitch(df)
    assert set(t.columns) == {"Pitch", "xwOBAcon", "BBE"}
    # el Fastball (batazo duro) tiene mayor xwOBAcon que el Slider
    fb = t.loc[t["Pitch"] == "Fastball", "xwOBAcon"].iloc[0]
    sl = t.loc[t["Pitch"] == "Slider", "xwOBAcon"].iloc[0]
    assert fb > sl
```

- [ ] **Step 2: Correr → falla; implementar en `core/expected.py`**

```python
def xwoba_against_by_pitch(df, grid=None):
    """xwOBACON contra por tipo de pitcheo (solo batazos), ascendente. Pitch/xwOBAcon/BBE."""
    cols = ["Pitch", "xwOBAcon", "BBE"]
    if "TaggedPitchType" not in df.columns:
        return pd.DataFrame(columns=cols)
    rows = []
    for pt, g in df.groupby("TaggedPitchType"):
        xbb = expected_batted_balls(g, grid)
        if xbb.empty:
            continue
        rows.append({"Pitch": pt, "xwOBAcon": round(float(xbb["xwoba"].mean()), 3),
                     "BBE": int(len(xbb))})
    return (pd.DataFrame(rows).sort_values("xwOBAcon").reset_index(drop=True)
            if rows else pd.DataFrame(columns=cols))
```

Run: `.venv/bin/python -m pytest core/tests/test_expected.py -q` → PASS.

- [ ] **Step 3: Wiring en `render_pitching`** — agregar tarjeta en el `tab1` (Summary), después de la tarjeta DISCIPLINA (dentro de `with tab1:`):

```python
        with viz_card("VALOR ESPERADO CONTRA", "xwOBA-contra por tipo de pitcheo",
                      "Calidad de contacto esperada que permite cada pitcheo (menor = mejor)."):
            xgrid = get_expected_grid(master_df, _grid_key(master_df))
            xw_pa = xwoba_pa(pf, xgrid)
            st.metric("xwOBA-contra (total)", fmt(xw_pa, "", 3))
            xw_tbl = xwoba_against_by_pitch(pf, xgrid)
            if xw_tbl.empty:
                st.info("Sin batazos con EV/ángulo para estimar valor.")
            else:
                st.dataframe(xw_tbl, use_container_width=True, hide_index=True)
            st.caption(_xgrid_note(xgrid))
```

- [ ] **Step 4: Wiring en `build_league_hitting_avg`** — agregar fila xwOBA. Después de la fila `{"Metric":"wOBA",...}` (línea ~842), insertar en la lista `rows`:

```python
        {"Metric":"xwOBA","League":fmt(xwoba_pa(df),"",3),"Median":"—","Max":"—"},
```

- [ ] **Step 5: Verificar sintaxis + import + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: ok, import ok, todos pasan.

- [ ] **Step 6: Commit**

```bash
git add core/expected.py core/tests/test_expected.py trackman_app.py
git commit -m "feat: xwOBA-contra en Pitching y xwOBA en benchmark de League"
```

---

### Task 6: Verificación visual + changelog

- [ ] **Step 1: Captura Playwright** de Hitting (tarjeta VALOR ESPERADO) y Pitching (VALOR ESPERADO CONTRA) con el script de captura (adaptar `capture_pitch_league.py`, que ya navega a Pitching; agregar navegación a Hitting). Verlas: valores en rango sensato (xwOBA ~0.2–0.5), tarjetas consistentes con iter 6.
- [ ] **Step 2: Iterar** copy/espaciado si hace falta.
- [ ] **Step 3: Changelog** v4.15 en `README.md` (capa evaluativa: xwOBA/xBA/xSLG, modelo híbrido MLB+liga, expected-vs-actual).
- [ ] **Step 4: Sign-off del founder → merge** a `main` (push → PR → merge → borrar rama → sync → tests).

---

## Self-Review

**1. Spec coverage:** modelo híbrido (Tasks 1,3) · x-stats por batazo/PA (Task 2) · Hitting VALOR ESPERADO (Task 4) · Pitching xwOBA-contra (Task 5) · League xwOBA (Task 5) · flag recalibración (Task 3 + notes en 4/5) · tests anclas/monotonía/PA/shrinkage (Tasks 1-3) · verificación visual (Task 6). ✓ Run value queda para Fase B (fuera de alcance, correcto).
**2. Placeholder scan:** Task 6 Step 1 dice "adaptar `capture_pitch_league.py`" — reuso de script de UI, inevitable en automatización visual; el resto con código completo. Constantes del modelo (`0.58`, centros) marcadas como ajustables por TDD en Task 1 Step 4 — es el bucle TDD esperado, no un placeholder.
**3. Type consistency:** `grid` es siempre el dict `{"cells","n","recalibrated"}` de `empirical_grid`; `xwoba_contact/expected_batted_balls/hybrid_outcome_probs` lo consumen igual. `_grid_key`/`get_expected_grid`/`_xgrid_note` con firma consistente en Hitting y Pitching. `expected_summary` devuelve las claves que consume la tarjeta. `xwoba_against_by_pitch` → columnas Pitch/xwOBAcon/BBE usadas en el dataframe. ✓

# Iteración 2 — Whiff%/CSW% por zona (grid interactivo)

**Fecha:** 2026-07-15
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Segundo corte vertical de la iniciativa "visualización más completa" sobre el modo **Pitching**.

## Contexto

Continúa la hoja de ruta de Pitching. La iter 1 extrajo la analítica a `core/` + `viz/`, migró los 6
gráficos a Plotly y agregó el Panel de Arsenal "Stuff" con **CSW% por tipo** (agregado). Esta iter 2
añade la **dimensión espacial**: dónde en la zona el pitcher consigue sus swing-and-miss y called
strikes, por tipo de pitcheo.

Hoja de ruta: **iter 1 (hecha)** → **iter 2 (este doc)** → iter 3 (secuenciación y tunneling).

## Objetivo

Un grid interactivo 5×5 sobre la zona que muestra **Whiff%** o **CSW%** por celda, con selector de
tipo de pitcheo y toggle de métrica, en un tab nuevo del modo Pitching. Robusto para muestras chicas
de amateur (guarda de muestra mínima por celda).

## Decisiones de diseño (aprobadas)

- **Representación:** grid de celdas por **tasa** (no densidad de frecuencia).
- **Métrica:** **Whiff%** y **CSW%**, con **toggle** (una vista, el analista alterna).
- **Granularidad:** **selector de tipo de pitcheo** (+ "Todos").
- **UI:** **tab nuevo "🎯 Whiff/CSW"** en el modo Pitching.
- **Guarda de muestra:** celda confiable si Whiff ≥ 4 swings / CSW ≥ 5 pitcheos; por debajo se
  atenúa (gris, solo el conteo).

## Analítica nueva — `core/pitching.py`

`whiff_csw_zone_grid(df, min_swings=4, min_pitches=5) -> dict` (puro; pandas/numpy; JSON-serializable).

### Geometría del grid (5×5, vista catcher)
El **3×3 interno se alinea a la zona de strike**:
- Bordes en x (ft): `[-1.383, -0.83, -0.277, 0.277, 0.83, 1.383]` → el centro 3 columnas cubren
  `[-0.83, 0.83]` (ancho de zona `2·ZONE_HALF_WIDTH`), una banda externa de una celda por lado.
- Bordes en z (ft): `[0.833, 1.5, 2.167, 2.833, 3.5, 4.167]` → el centro 3 filas cubren
  `[1.5, 3.5]` (`ZONE_BOTTOM..ZONE_TOP`), banda externa de una celda arriba y abajo.
- **Banda externa sin límite:** los pitcheos fuera del extent se asignan (clamp) a la celda de borde
  más cercana, de modo que **todo pitcheo con ubicación** cae en una celda (la banda externa es el
  área de chase/waste). Índice de celda por eje = `clip(digitize(coord, edges)-1, 0, 4)`.

Las constantes de zona vienen de `core.metrics` (`ZONE_HALF_WIDTH=0.83`, `ZONE_BOTTOM=1.5`,
`ZONE_TOP=3.5`). Los bordes externos = borde de zona ± una celda (celda_x = `2·0.83/3`,
celda_z = `2.0/3`).

### Métricas por celda
Para cada una de las 25 celdas, contando los pitcheos (con ubicación y `PitchCall`) que caen en ella:
- `n_pitches` — pitcheos en la celda.
- `n_swings` — swings en la celda (`PitchCall ∈ SWING_CALLS`).
- `whiffs` — `PitchCall == "StrikeSwinging"`.
- `called` — `PitchCall == "StrikeCalled"`.
- `whiff_pct` = `safe_pct(whiffs, n_swings)` — denominador = swings.
- `csw_pct` = `safe_pct(called + whiffs, n_pitches)` — denominador = pitcheos.
- `whiff_reliable` = `n_swings >= min_swings`.
- `csw_reliable` = `n_pitches >= min_pitches`.

### Estructura de retorno
```python
{
  "x_edges": [...6 floats...],
  "z_edges": [...6 floats...],
  "cells": [   # 25 celdas, fila-mayor o con índices (ix, iz) explícitos
    {"ix": int, "iz": int,
     "n_pitches": int, "n_swings": int, "whiffs": int, "called": int,
     "whiff_pct": float, "csw_pct": float,
     "whiff_reliable": bool, "csw_reliable": bool},
    ...
  ],
  "total_pitches": int,   # pitcheos con ubicación considerados
}
```
Si faltan `PlateLocSide`/`PlateLocHeight` o `PitchCall`, o no hay pitcheos con ubicación, devuelve
`{"x_edges": [...], "z_edges": [...], "cells": [], "total_pitches": 0}` (el viz lo trata como vacío).
`TaggedPitchType` **no** es requerido por esta función (el filtrado por tipo se hace en la UI antes de
llamarla), así que no debe lanzar por su ausencia.

## Viz nuevo — `viz/pitching.py`

`zone_rate_heatmap(grid, metric, name) -> go.Figure`, con `metric ∈ {"whiff", "csw"}`.

- Si `grid["cells"]` está vacío → `theme.empty_fig("No hay datos de ubicación/PitchCall")`.
- `go.Heatmap` 5×5 usando `x_edges`/`z_edges` para posicionar las celdas (o `go.Heatmap` con
  `x`/`y` de centros de celda). Valor `z` = la tasa de la métrica elegida (`whiff_pct` o `csw_pct`).
- **Escala de color** blanco→rojo estilo Savant (`[[0,"#ffffff"],[0.5,"#f6b6a8"],[1,"#D22D49"]]`),
  `zmin=0`, `zmax=100`.
- **Celdas no confiables** (según la métrica activa): se muestran en gris tenue y con **solo el
  conteo** (sin color de tasa) — implementado con una máscara (`z=None`/`NaN` para esas celdas y una
  capa/anotación gris de fondo, o texto gris). Nunca pintan una tasa engañosa.
- **Texto por celda:** `"{rate:.0f}%\n(n)"` en celdas confiables; `"(n)"` gris en no confiables;
  vacío si `n_pitches == 0`.
- **Overlay:** rectángulo real de la zona (`theme.strike_zone_shapes()`), ejes en vista catcher con
  rango que cubra el grid (`x ∈ [-1.5,1.5]`, `z ∈ [0.7,4.3]`), `scaleanchor` para aspecto igual.
- **Hover:** tipo de métrica, tasa, numerador/denominador (`whiffs/swings` o `(called+whiffs)/pitches`),
  `n`, y si la celda es no confiable ("muestra baja").
- Título vía `theme.base_layout(...)` (consistente con los otros builders).

## UI — `trackman_app.py` (`render_pitching`)

Se agrega un tab. La llamada `st.tabs([...])` pasa de 4 a **5 tabs**:
`["📋 Summary", "📍 Location", "📊 Trends", "🎯 Whiff/CSW", "🏟️ Stadium"]`.

En el tab **"🎯 Whiff/CSW"**:
1. `st.selectbox` "Tipo de pitcheo" con los tipos presentes en `pf` + opción **"Todos"**
   (key `whiffcsw_ptype`).
2. `st.radio` "Métrica" con `["Whiff %", "CSW %"]` (key `whiffcsw_metric`), horizontal.
3. `sub = pf if tipo == "Todos" else pf[pf["TaggedPitchType"] == tipo]`.
4. `grid = whiff_csw_zone_grid(sub)`; `metric = "whiff" if radio == "Whiff %" else "csw"`.
5. `st.plotly_chart(vpitch.zone_rate_heatmap(grid, metric, f"{selected} · {tipo}"),
   use_container_width=True)`.
6. Caption con el `total_pitches` considerado y nota de la guarda de muestra.

No se modifican los otros tabs ni `export_pitching_pdf` (el grid nuevo no entra al PDF en esta iter).

## Manejo de errores / borde
- Sin `PlateLocSide`/`PlateLocHeight` o `PitchCall` → `whiff_csw_zone_grid` devuelve celdas vacías;
  el viz muestra estado vacío.
- Celda con `n_pitches == 0` → sin texto ni color (blanco).
- Denominadores 0 → `safe_pct` los protege.
- Toggle/selector con keys propios en `st.session_state`; no colisionan con el checkbox del Arsenal.

## Testing
- `core/tests/test_pitching.py` (añadir):
  - Grid con ubicaciones/PitchCall sintéticos colocados en celdas conocidas → asertar `whiff_pct`,
    `csw_pct` exactos de esas celdas y sus numeradores/denominadores.
  - Celda con 1 swing → `whiff_reliable == False`; celda con <5 pitcheos → `csw_reliable == False`.
  - Pitcheo fuera del extent → cae (clamp) en la celda de borde correcta.
  - Falta de columnas (`PitchCall`/ubicación) → retorno con `cells == []`, sin lanzar.
- `viz/tests/test_pitching_viz.py` (añadir):
  - `zone_rate_heatmap(grid, "whiff", ...)` y `("csw", ...)` con grid real → `go.Figure`.
  - grid vacío → `go.Figure` con `annotations` (empty_fig).
- Suite completa: `.venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`.

## No-goals (YAGNI)
- Solo Pitching. Sin tunneling (iter 3), sin small-multiples por tipo, sin cambios a Hitting/League.
- Sin incluir el grid nuevo en el export PDF en esta iteración.
- Sin cambiar la representación (queda gridded; nada de KDE continuo).

## Criterios de aceptación
- [ ] `whiff_csw_zone_grid` en `core/pitching.py`, pura, con tests (incl. reliability y clamp).
- [ ] `zone_rate_heatmap` en `viz/pitching.py`, degrada a `empty_fig`, con smoke tests.
- [ ] Tab "🎯 Whiff/CSW" en Pitching con selector de tipo + toggle de métrica, funcionando.
- [ ] Celdas no confiables atenuadas (no pintan tasa engañosa).
- [ ] Suite verde; sin regresión en los otros tabs/modos.

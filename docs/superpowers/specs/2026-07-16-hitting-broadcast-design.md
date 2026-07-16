# Iteración 4 — Hitting al mismo nivel (interactivo + spray broadcast)

**Fecha:** 2026-07-16
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Modo **🏏 Hitting** (`trackman_app.py`).

## Contexto

El modo Hitting está como estaba Pitching antes de la iter 1: toda la analítica y los gráficos
(matplotlib estáticos con `st.pyplot`) viven en `trackman_app.py`. El founder quiere llevarlo "al
mismo nivel": **(1) interactivo + arquitectura limpia** (extraer a `core/` + `viz/`, gráficos
Plotly) y **(2) look broadcast** para el spray chart. (No pidió métricas/vistas nuevas ni solo
pulido — eso queda fuera.)

Decisiones aprobadas:
- Spray broadcast **top-down** (cenital), campo **de día** (pasto verde).
- **Ambos** modos del spray: render **matplotlib foto-realista estático** (default) + **toggle a
  versión Plotly interactiva**.
- Color de batazos con **toggle EV ↔ resultado**.
- Los demás gráficos → **Plotly interactivo**.

## Arquitectura

Sigue el patrón de Pitching (iters 1-2):

```
core/hitting.py        # analítica pura de bateo (pandas/numpy, sin Streamlit/matplotlib)
viz/hitting.py         # builders Plotly interactivos del modo Hitting
viz/spray_render.py    # render matplotlib FOTO-REALISTA top-down del spray (PNG estático)
core/tests/test_hitting.py
viz/tests/test_hitting_viz.py
```

`viz/spray_render.py` usa matplotlib (como `viz/export.py`, que es la excepción de matplotlib en
`viz/`). `core/hitting.py` no importa Streamlit ni matplotlib.

### `core/hitting.py` — analítica (mover del monolito + helpers de spray)
Se **mueven** desde `trackman_app.py` (con alias para no romper call-sites al inicio):
- `build_hitting_monthly(df, lmeta=None)` — progresión mensual.
- `build_split_table(df, split_col="PitcherThrows", ev_hard=95)` — splits vs RHP/LHP.
- `compute_plate_discipline_batter(df)` — disciplina del bateador (K%/BB% por PA, Zone/Chase reales).
- `build_play_result_table(df)` — conteo de resultados de jugada por PA.
- `build_league_hitting_avg(df, lmeta=None)` — promedios de liga de bateo.

Nuevos helpers puros:
- `batted_balls(df)` — filas con contacto (usa `batted_ball_mask` de core.metrics); columnas EV/LA/Distance/Bearing/PlayResult limpias.
- `spray_points(df) -> dict` — por batazo con Distance/Bearing: `x = Distance*sin(bearing)`,
  `y = Distance*cos(bearing)`, más `ev`, `la`, `distance`, `result`. JSON-serializable (listo para API/React).
- `hitting_summary(df, lmeta) -> dict` — métricas de cabecera y del panel: `n`, `pa`, `avg_ev`,
  `max_ev`, `avg_la`, `hh_pct`, `barrel_pct`, `woba` (reusa `count_pa`, `barrel_mask`,
  `batted_ball_mask`, `compute_woba`, `safe_pct` de core.metrics).

Regla: `core/hitting.py` solo pandas/numpy + `core.metrics`.

### `viz/hitting.py` — builders Plotly (reemplazan los `plot_*` matplotlib)
Cada builder recibe DataFrames/dicts de `core` y devuelve `go.Figure`, degradando a
`theme.empty_fig(...)` si faltan datos. Usa `viz/theme.py` (tema Savant) ya existente.
- `ev_distribution(df, name)` — histograma de Exit Velocity.
- `la_distribution(df, name)` — histograma de Launch Angle.
- `ev_la_scatter(df, name)` — scatter EV vs LA, color por zona de daño/resultado, hover.
- `damage_zone(df, name)` — heatmap de EV/hard-hit por ubicación en la zona (Histogram2dContour ponderado).
- `rolling_ev(df, name, window=15)` — línea de EV rodante.
- `spray_interactive(points, name, color_by="ev")` — spray Plotly: campo estilizado (formas: tierra,
  pasto, barda en arco, bases, líneas de foul) + scatter de batazos con hover (EV/LA/distancia/resultado);
  `color_by ∈ {"ev","result"}`.

### `viz/spray_render.py` — spray foto-realista (matplotlib, estático)
`render_spray_png(points, summary, name, color_by="ev", night=False) -> bytes`:
- **Campo top-down realista de día:** pasto verde con **franjas de corte** (bandas radiales/verticales),
  infield de tierra (diamante + arco), warning track (anillo tan), **barda del outfield en arco**,
  bases (cuadros blancos), montículo, plato, líneas de foul.
- **Batazos** en su (x, y) coloreados por **EV** (mapa de calor coolwarm, vmin≈65 vmax≈112) o por
  **resultado** (1B/2B/3B/HR/Out con paleta), según `color_by`.
- **Panel de bateo** fijo a un lado (estilo PITCH ARSENAL, reusa el patrón visual): nombre del bateador,
  "BATTED BALL PROFILE", y filas: **Avg EV, Max EV, Avg LA, HH%, Barrel%, wOBA**.
- Devuelve PNG bytes (para `st.image` y para el PDF).
- Marca de distancia (p.ej. "400 ft" al CF). `night=False` por defecto (día); el flag existe por
  consistencia futura pero no se expone en la UI de esta iteración.

## UI — `render_hitting` (`trackman_app.py`)

`render_hitting` queda delgado (core → viz → Streamlit). Cambios:
- Métricas de cabecera desde `hitting_summary`. Plate discipline se mantiene.
- Los `st.pyplot(...)` de los tabs se cambian a `st.plotly_chart(...)` usando `viz.hitting.*`
  (EV/LA dist, EV/LA scatter, damage, rolling EV).
- **Tab de Spray:** un `st.radio` "Vista" (**🖼️ Pro** [matplotlib estático] / **🔍 Interactivo**
  [Plotly]) y un `st.radio` "Color" (**Exit Velocity** / **Resultado**). Pro → `st.image(render_spray_png(...))`;
  Interactivo → `st.plotly_chart(spray_interactive(...))`. Ambos con el `color_by` elegido.

## PDF

`export_hitting_pdf` se mantiene (matplotlib). El spray del PDF usa `render_spray_png` (ya es un PNG
matplotlib) embebido vía el `_fig_to_img`/pipeline existente, o directamente como imagen. Las demás
figuras del PDF: se pueden dejar con los builders matplotlib actuales para el PDF **o** convertir vía
kaleido (como Pitching). Para acotar riesgo, esta iter usa el spray PNG en el PDF y conserva el resto
del PDF de hitting como está; unificar el PDF de hitting a kaleido es un follow-up.

## Manejo de errores / borde
- Sin `Distance`/`Bearing` → spray vacío con mensaje. Sin `ExitSpeed`/`Angle` → distribuciones/scatter
  con estado vacío. Denominadores protegidos con `safe_pct`.
- `spray_points`/`batted_balls` no lanzan por columnas faltantes (devuelven vacío).

## Testing
- `core/tests/test_hitting.py`: `spray_points` (x/y correctos desde Distance/Bearing conocidos),
  `hitting_summary` (EV/HH%/barrel/woba con datos sintéticos), y **regresión** de `build_split_table`/
  `build_hitting_monthly` (misma salida que el monolito sobre una muestra).
- `viz/tests/test_hitting_viz.py`: cada builder Plotly devuelve `go.Figure` (normal y vacío).
- `viz/tests/test_spray_render.py`: `render_spray_png` devuelve PNG bytes (por EV y por resultado);
  df sin Distance/Bearing → PNG de estado vacío o `None` sin lanzar.
- Suite: `.venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`.

## No-goals (YAGNI)
- Sin expected stats (xBA/xwOBA) ni métricas nuevas.
- Sin tocar Pitching / League / Top Plays / Trayectorias 3D.
- Sin unificar el PDF de hitting a kaleido (follow-up).
- Sin versión de noche del spray en la UI (day por ahora).

## Criterios de aceptación
- [ ] `core/hitting.py`, `viz/hitting.py`, `viz/spray_render.py` creados; `core/` sin Streamlit/matplotlib.
- [ ] Los 5 gráficos estándar de Hitting son Plotly interactivos.
- [ ] Spray broadcast: estático pro (matplotlib top-down día) + toggle interactivo (Plotly) + toggle EV/resultado + panel de bateo.
- [ ] `render_hitting` delgado; suite verde; sin regresión en otros modos.
- [ ] Verificación visual del spray (render→comparar) con sign-off del founder.

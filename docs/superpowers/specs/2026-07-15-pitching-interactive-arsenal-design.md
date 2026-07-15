# Iteración 1 — Pitching interactivo + Panel de Arsenal "Stuff"

**Fecha:** 2026-07-15
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Primer corte vertical de la iniciativa "visualización más completa" sobre el modo **Pitching**.

## Contexto y motivación

`trackman_app.py` es un archivo único de ~2,364 líneas con la analítica mezclada con la UI de
Streamlit. La visión acordada es hacer el sistema **más completo** en tres dimensiones:
interactividad, profundidad analítica y vistas nuevas. La estrategia de plataforma elegida es
**híbrido por fases**: seguir en Streamlit ahora, pero extraer la analítica a un paquete limpio
(como ya existe en `trajectory/`) para que un frontend React pueda montarse encima después sin
reescribir la lógica.

Esta es la **iteración 1** de una secuencia sobre Pitching:

| Iter | Entregable |
|------|-----------|
| **1 (este doc)** | Extraer analítica de Pitching + 6 gráficos → Plotly + Panel de Arsenal "Stuff" (incl. CSW% por tipo) |
| 2 | Whiff%/CSW% por zona (heatmaps interactivos por tipo y ubicación) |
| 3 | Secuenciación y tunneling (se apoya en `trajectory/`) |

## Objetivos de la iteración 1

1. Crear los paquetes `core/` (analítica pura) y `viz/` (figuras Plotly), estableciendo el
   patrón que replicarán las iteraciones/modos siguientes.
2. Migrar los 6 gráficos del modo Pitching de matplotlib/seaborn a **Plotly interactivo**
   (hover, zoom).
3. Construir el **Panel de Arsenal "Stuff"**: plot de movimiento interactivo + tabla de arsenal
   con la métrica nueva **CSW%**.
4. Unificar la generación de gráficos: el PDF export usa las mismas figuras Plotly (vía kaleido).
5. `render_pitching` queda delgado (orquesta `core` → `viz` → Streamlit).

## No-objetivos (YAGNI para esta iteración)

- Whiff%/CSW% por **zona** (heatmaps por ubicación) → iteración 2.
- Secuenciación / tunneling → iteración 3.
- Migrar los modos Hitting / League / Top Plays.
- Frontend React (la extracción deja el terreno listo, pero no se construye aquí).
- Rediseño estético general (el pulido de look quedó en segundo plano).

## Arquitectura

Dos paquetes nuevos, mismo patrón que `trajectory/` (analítica desacoplada de la UI):

```
core/                    # analítica PURA — pandas/numpy, cero Streamlit
  __init__.py
  metrics.py             # primitivos compartidos movidos del monolito
  pitching.py            # métricas de pitching
  tests/
    __init__.py
    test_pitching.py

viz/                     # constructores de figuras Plotly — DataFrame → go.Figure
  __init__.py
  theme.py               # tema estilo Baseball Savant para Plotly
  pitching.py            # figuras del modo pitching
  export.py              # fig_to_png(fig) vía kaleido (para el PDF)
```

### `core/metrics.py` — primitivos compartidos

Se **mueven** (no se copian) desde `trackman_app.py` a `core/metrics.py`, y el monolito los
importa desde ahí. Cambio mecánico de bajo riesgo (borrar def local + `from core.metrics import …`).

Funciones/constantes a mover: `safe_pct`, `count_pa`, `in_zone_mask`, `batted_ball_mask`,
`barrel_mask`, `count_k_bb`, `pitch_color` (con sus constantes de color `STATCAST_PITCH_COLORS`
y `PITCH_PALETTE`, que son strings hex puros — sin matplotlib), y las constantes `SWING_CALLS`,
`CONTACT_CALLS` (y las que ellas dependan). Se mueven solo primitivos usados de forma
transversal; las funciones específicas de hitting/league se dejan en el monolito hasta su propia
iteración. El colormap `_PCT_CMAP` (que sí usa matplotlib) **se queda** en el monolito.

**Regla:** `core/` no importa Streamlit ni matplotlib. Solo pandas/numpy.

### `core/pitching.py` — métricas de pitching

Funciones puras `DataFrame → DataFrame/dict`:

- `pitch_summary(df) -> DataFrame` — porta `build_pitch_summary`: por tipo → Count, Usage%,
  Avg/Max mph, Spin, IVB, HB. Orden: fastballs primero, luego por Count.
- `pitch_discipline(df) -> DataFrame` — porta `compute_pitch_discipline`: por tipo → Zone%,
  Swing%, Contact%, Chase%, Whiff%. Usa ubicación real cuando existe, si no aproxima por
  `PitchCall` (comportamiento actual preservado).
- `arsenal_stuff(df) -> DataFrame` — **nuevo**: combina `pitch_summary` + `pitch_discipline`
  y añade **CSW%**. Una fila por tipo con todas las columnas del arsenal.
- `movement_points(df) -> dict` — **nuevo**: devuelve, por tipo, los puntos individuales
  (HB, IVB) y el centroide (mean HB, mean IVB, n, usage%, avg velo, max velo, avg spin,
  whiff%, CSW%) para alimentar el plot de movimiento. Estructura JSON-serializable (lista para
  una futura API).

**Definición CSW%** = (StrikeCalled + StrikeSwinging) / pitcheos del tipo.
**Definición Whiff%** (existente) = StrikeSwinging / swings, donde swings = `SWING_CALLS`.
Denominadores protegidos con `safe_pct` (retorna 0.0 si denom = 0).

### `viz/theme.py` — tema Plotly estilo Savant

- Paleta de tipos de pitcheo tomada de `core.metrics.pitch_color` (mismos colores Statcast que
  hoy) para consistencia con el resto del app y con el modo Trayectorias 3D.
- Layout base: fondo blanco, grid gris tenue, tipografía y márgenes consistentes.
- Helpers de formas reutilizables: `strike_zone_shapes()` (rectángulo de zona ±0.83 ft ×
  1.5–3.5 ft) y `home_plate_shape()`; anillos concéntricos de 6" para el plot de movimiento.
- `empty_fig(msg)` — figura de estado vacío con mensaje centrado (reemplaza los
  `ax.text(...,"No data")` actuales).

### `viz/pitching.py` — figuras Plotly

Cada builder recibe DataFrames/dicts ya calculados por `core` (no calcula métricas) y devuelve
`go.Figure`. Todos manejan datos faltantes devolviendo `empty_fig(...)`.

| Builder | Reemplaza a | Notas |
|---------|-------------|-------|
| `movement_bubble(points)` | `plot_movement_profile` | Bubble por tipo (tamaño ∝ usage%), anillos 6", hover completo, toggle de pitcheos individuales |
| `location_scatter(df)` | `plot_pitch_locations` | Scatter + forma de zona, color por tipo, hover velo/tipo |
| `hot_zone(df)` | `plot_hot_zone` | Densidad 2D (`Histogram2dContour`) sobre la zona |
| `location_by_pitch(df)` | `plot_location_by_pitch` | Subplots facetados por tipo (máx. 6) |
| `velo_trend(df)` | `plot_velocity_tendency` | Velo vs fecha, hover; línea por tipo |
| `usage_heatmap(tab)` | `plot_usage_by_count` | Heatmap con anotaciones (recibe tabla de `build_usage_by_count`) |

`build_usage_by_count` (transformación pura) se mueve también a `core/pitching.py`.

### `viz/export.py` — PDF

- `fig_to_png(fig, scale=2) -> bytes` — Plotly → PNG vía `kaleido`.
- **Guarda de robustez:** si `kaleido` no está disponible o falla en runtime (riesgo conocido
  en Streamlit Cloud), `fig_to_png` captura la excepción y el generador de PDF omite ese gráfico
  con una nota ("gráfico no disponible en este entorno"), sin romper el reporte ni el resto del
  app. Se registra un `st.warning` una sola vez.
- `export_pitching_pdf` se adapta para recibir figuras Plotly y usar `fig_to_png`. Las funciones
  `_pdf_two_charts` / `_pdf_single_chart` se ajustan para PNGs de Plotly.
- `kaleido` se agrega a `requirements.txt`.

## Cambios en la UI (`trackman_app.py`)

`render_pitching` se reescribe delgado. Estructura de tabs resultante:

- **📋 Summary** — Panel de Arsenal "Stuff": `movement_bubble` (arriba) + tabla `arsenal_stuff`
  (reemplaza la tabla de arsenal actual, ahora con CSW%). Debajo, la tabla de disciplina.
- **📍 Location** — `location_scatter` + `hot_zone` + `location_by_pitch` (todos Plotly).
- **📊 Trends** — `velo_trend` + `usage_heatmap`. (El plot de movimiento **sale** de aquí; ahora
  vive en Summary como parte del Arsenal, sin duplicar.)
- **🏟️ Stadium** — sin cambios (sigue "coming soon"; no es parte de esta iteración).

Las métricas de cabecera, la sección de percentiles Savant y el selector de pitcher se mantienen.
Cada `st.pyplot(...)` de pitching se cambia a `st.plotly_chart(fig, use_container_width=True)`.

## Manejo de errores / casos borde

- **Columnas faltantes** (IVB/HB, PitchCall, PlateLoc): cada builder de `viz` devuelve
  `empty_fig(mensaje)` — se preserva el comportamiento actual de "No movement data" etc.
- **Muestra baja**: se mantiene la advertencia `n < 15` existente.
- **Denominadores 0**: `safe_pct` los protege (Whiff%/CSW%/Chase% → 0.0).
- **kaleido no disponible**: PDF omite el gráfico con nota; no rompe.
- **`Count` (balls-strikes) ausente**: `usage_heatmap` devuelve estado vacío.

## Testing

`core/tests/test_pitching.py` (pytest, en línea con los 18 tests de `trajectory/`):

1. **CSW% / Whiff%**: con `PitchCall` sintético (mezcla StrikeCalled/StrikeSwinging/FoulBall/
   InPlay/BallCalled) verificar valores exactos esperados.
2. **`arsenal_stuff`**: forma correcta (una fila por tipo), columnas presentes, orden FB primero.
3. **`movement_points`**: centroides = media de los puntos por tipo; usage% suma ~100%.
4. **Regresión de extracción**: sobre un DataFrame de muestra, `core.pitching.pitch_summary` y
   `pitch_discipline` producen salida idéntica a las funciones originales del monolito (garantiza
   que mover el código no cambió resultados).

Smoke tests de `viz/pitching.py`: cada builder devuelve `go.Figure` (a) con df normal y (b) con
df vacío/columnas faltantes, sin lanzar excepción.

Comando: `pytest core/tests/ -v`.

## Riesgos

- **kaleido en Streamlit Cloud**: dependencia con historial de fricción en despliegue. Mitigado
  por la guarda de `viz/export.py` (degradación elegante). Verificar en despliegue tras la iter 1.
- **Mover primitivos compartidos** podría afectar a hitting/league si un import queda mal.
  Mitigado por el test de regresión y por correr el app completo antes de cerrar la iteración.

## Criterios de aceptación

- [ ] Paquetes `core/` y `viz/` creados; `core/` sin dependencias de Streamlit/matplotlib.
- [ ] Los 6 gráficos de Pitching se renderizan como Plotly interactivo en el app.
- [ ] Panel de Arsenal "Stuff" visible en Summary con plot + tabla incluyendo CSW%.
- [ ] PDF de pitching se genera con las figuras Plotly (o degrada elegante si falta kaleido).
- [ ] `pytest core/tests/ -v` pasa (incluye test de regresión de extracción).
- [ ] El app corre end-to-end sin regresiones en los otros modos (hitting/league/top plays/3D).

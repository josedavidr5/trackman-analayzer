# `trajectory/` — Módulo de trayectorias de pitcheo

Paquete **independiente** (no acoplado al dashboard): motor físico, validación, analítica y API Flask. El frontend Streamlit y la API consumen las mismas funciones de `analytics.py`.

```
trajectory/
├── engine.py        # física: compute_pitch_path, pitch_metrics
├── validation.py    # schema + rangos físicos (errores de captura → NaN)
├── analytics.py     # movement profile, release consistency, trends, payloads
├── api.py           # Flask: create_app(csv_paths=[...]) / create_app(data_frame=df)
└── tests/           # pytest — 18 tests (física + API)
```

## Motor (`engine.py`)

`compute_pitch_path(pitch_row, n_points=50) -> [(x,y,z,t), …]`

Coordenadas vista-catcher: x horizontal (ft), y distancia al plato (release≈54, plato=1.417), z altura (ft). Dos modos:

- **kinematic** — si el CSV trae el paquete 9P (`x0,y0,z0,vx0,vy0,vz0,ax0,ay0,az0`), integra movimiento con aceleración constante (gravedad+Magnus+drag ya capturados por TrackMan).
- **inferred** — con release/velo/break/ubicación resuelve las aceleraciones que reproducen exactamente los valores reportados (los tests lo verifican a <0.01 ft).

`pitch_metrics(pitch_row)` → `flight_time`, `vaa_deg`, `haa_deg`, `plate_speed_mph`, `spin_efficiency` (estimada por inversión del coeficiente de lift — aproximación documentada), `model`.

## Validación (`validation.py`)

- `validate_schema(df)` → campos faltantes del schema y si el dataset está `trajectory_ready`.
- `validate_physical(df)` → valores fuera de rango físico (ej. RelSpeed>110 mph) se marcan NaN y se reporta `{columna: n_invalidos}`. Nunca se descartan filas completas.

## API Flask (`api.py`)

```bash
python -m trajectory.api datos/torneo1.csv datos/torneo2.csv   # puerto 5001
```

> El dashboard corre en Streamlit Cloud (no hospeda Flask). Esta API es para integraciones externas o migración futura a cliente-servidor.

Filtros comunes en query string: `date_from`, `date_to` (YYYY-MM-DD), `pitch_type`, `count` (ej. `1-2`), `batter_side` (`R`/`L`), `result` (`strike`/`ball`/`hit`).

### `GET /api/pitch/<pitch_id>/trajectory?n_points=50`

```
GET /api/pitch/abc123/trajectory?n_points=5
```
```json
{
  "pitch_id": "abc123",
  "meta": {"Pitcher": "Juan Perez", "TaggedPitchType": "4-Seam", "RelSpeed": 95.0,
           "SpinRate": 2400, "PlateLocSide": 0.2, "PlateLocHeight": 2.8, "...": "..."},
  "metrics": {"flight_time": 0.3952, "vaa_deg": -4.88, "haa_deg": 3.05,
              "plate_speed_mph": 86.9, "spin_efficiency": 0.686, "model": "inferred"},
  "n_points": 5,
  "trajectory": [
    {"x": -1.8,  "y": 54.0,   "z": 5.9,  "t": 0.0},
    {"x": -1.425,"y": 40.39,  "z": 5.35, "t": 0.0988},
    {"x": -0.967,"y": 27.09,  "z": 4.64, "t": 0.1976},
    {"x": -0.425,"y": 14.10,  "z": 3.80, "t": 0.2964},
    {"x": 0.2,   "y": 1.4167, "z": 2.8,  "t": 0.3952}
  ]
}
```
Errores: `404` pitch no encontrado · `422` datos insuficientes para reconstruir.

### `GET /api/pitcher/<pitcher_id>/pitches?date_from&date_to&pitch_type&count&batter_side&result`

```
GET /api/pitcher/Juan Perez/pitches?pitch_type=Slider&date_from=2026-06-10
```
```json
{"pitcher": "Juan Perez", "n": 12,
 "pitches": [{"PitchUID": "u7", "TaggedPitchType": "Slider", "RelSpeed": 84.2,
              "Date": "2026-06-11", "PlateLocSide": -0.5, "...": "..."}]}
```

### `GET /api/pitcher/<pitcher_id>/movement_profile`

```json
{"pitcher": "Juan Perez", "vertical_break_col": "InducedVertBreak",
 "pitches":   [{"pitch_type": "4-Seam", "hb": 8.1, "vb": 16.3, "velo": 94.8}],
 "centroids": [{"pitch_type": "4-Seam", "hb": 7.9, "vb": 15.8, "n": 28}]}
```

### `GET /api/pitcher/<pitcher_id>/release_consistency`

```json
{"pitcher": "Juan Perez",
 "points":  [{"date": "2026-06-11", "rel_side": -1.72, "rel_height": 5.84, "pitch_type": "4-Seam"}],
 "by_date": [{"date": "2026-06-11", "n": 22, "mean_side": -1.71, "mean_height": 5.85,
              "std_side": 0.08, "std_height": 0.06}],
 "summary": {"n": 40, "std_side": 0.09, "std_height": 0.07, "std_total": 0.114,
             "drift_first_to_last_ft": 0.041}}
```
`std_total` alto o `drift_first_to_last_ft` creciente ⇒ posible fatiga o cambio mecánico.

### `GET /api/pitcher/<pitcher_id>/velocity_spin_trends`

```json
{"pitcher": "Carlos Diaz",
 "outings": [{"date": "2026-06-05", "pitch_type": "4-Seam", "n": 14,
              "avg_velo": 91.3, "max_velo": 93.8, "avg_spin": 2280.0, "max_spin": 2410.0}]}
```

## Tests

```bash
pytest trajectory/tests/ -v      # 18 tests: física consistente con TrackMan + API
```

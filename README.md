# Trackman Analyzer — v4.2 (Savant Edition)

Dashboard de análisis de datos TrackMan de béisbol construido con Streamlit, con diseño inspirado en Baseball Savant.

## Cómo correrlo

```bash
pip install -r requirements.txt
streamlit run trackman_app.py
```

## Fuentes de datos

**⬆️ Upload CSVs** — sube uno o varios CSVs de TrackMan. El app los une, limpia y deduplica nombres de jugadores automáticamente.

**🏆 Tournament Folder** — apunta el app a una carpeta local. Cada subcarpeta es un torneo (ej. `Torneos/Copa Norte 2026/*.csv`). El app detecta cambios en los archivos (agregar, editar o corregir un nombre) y se actualiza automáticamente en la siguiente interacción — sin limpiar caché manualmente.

## Modos

- **⚾ Pitching** — arsenal, disciplina, ubicaciones, heatmaps por tipo de pitcheo, uso por conteo, tendencia de velocidad, perfil de movimiento.
- **🏏 Hitting** — progresión mensual, rolling EV, splits vs RHP/LHP, resultados de jugada, spray chart, damage zone, distribuciones EV/LA, wOBA.
- **📊 League** — promedios de liga de pitcheo y bateo con benchmarks por nivel.
- **🔥 Top Plays** — escribe tu propia pregunta en español o inglés ("top 5 batazos más fuertes de la semana en Estadio Norte", "lanzamientos más rápidos en cada región", "barrels de Pedro Ruiz este mes") o usa las preguntas rápidas. El parser entiende métrica, periodo, top N, jugador, estadio y región. Rankings por periodo, por estadio y **por región**, y **tarjetas 1080×1080 listas para redes sociales** (PNG descargable, una por región si lo pides).

### Regiones

Agrupa estadios en regiones de dos formas: edita la tabla en el expander "🗺️ Configurar regiones" dentro de Top Plays (y descarga el `regions.csv` generado), o coloca un `regions.csv` con columnas `Stadium,Region` en la carpeta del torneo — se carga automáticamente.

## Niveles de juego

El selector Pro / College / High School / Mixed ajusta todos los umbrales (Hard Hit, barrel, velo) en todas las tablas y gráficas.

## Metodología (v4.2)

- **K% y BB%** se calculan por aparición al plato (PA), no por pitcheo. Un PA = pitcheo con resultado terminal (1B, 2B, 3B, HR, Out, K, BB, HBP, etc.).
- **BB** viene de `PlayResult` — una bola cantada NO cuenta como base por bolas.
- **Zone% / Chase%** usan la ubicación real del pitcheo (`PlateLocSide`/`PlateLocHeight`, zona ±0.83 ft × 1.5–3.5 ft). Si no hay datos de ubicación, se usa la aproximación por `PitchCall`.
- **Barrel%** usa la definición dinámica estilo Savant (EV ≥ 98 abre ventana de LA 26–30° que se amplía con cada mph hasta 8–50°), reescalada por nivel de juego, sobre **batazos en juego** (no todos los pitcheos).
- **Hard Hit%** se calcula sobre batazos en juego con el umbral del nivel seleccionado.
- **wOBA** usa pesos lineales estándar (BB 0.69, HBP 0.72, 1B 0.89, 2B 1.27, 3B 1.62, HR 2.10).

## Columnas soportadas

`Pitcher, Batter, PitchCall, PlayResult, TaggedPitchType, RelSpeed, SpinRate, InducedVertBreak, HorzBreak, PlateLocSide, PlateLocHeight, ExitSpeed, Angle, Distance, Bearing, PitcherThrows, BatterSide, Stadium, Date, Balls, Strikes` — con alias comunes detectados automáticamente (ej. `KorBB → PlayResult`, `BallPark → Stadium`).

## Changelog v4.2

**Fixes**
- BB% ya no cuenta cada bola como walk (bug crítico)
- K%/BB% por PA en dashboard, tablas mensuales, splits y liga
- Zone%/Chase% desde ubicación real del pitcheo
- Barrel% con definición Savant dinámica y denominador de batazos en juego
- Benchmarks por nivel aplicados consistentemente en todas las tablas
- Parsing de fechas mes-primero (formato TrackMan US) con fallback

**Nuevo**
- Modo 🔥 Top Plays con preguntas rápidas y tarjetas PNG para redes
- Carpetas de torneo con auto-actualización al cambiar archivos
- Uso de pitcheos por conteo (heatmap)
- Rolling Exit Velocity
- Heatmaps de ubicación por tipo de pitcheo
- wOBA en hitting, splits y liga

**Rendimiento**
- Los PDFs se generan solo al presionar el botón (antes se regeneraban en cada interacción)

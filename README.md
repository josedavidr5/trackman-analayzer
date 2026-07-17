# Trackman Analyzer — v4.7 (Savant Edition)

## Limpieza de nombres (v4.7)

El app unifica automáticamente variantes del mismo jugador entre archivos: typos de una letra ("Jose Peres" → "Jose Perez"), acentos ("José Pérez"), iniciales ("J. Perez"), orden ("Perez, Jose") y mayúsculas. Toda la data del jugador se agrega bajo un solo nombre canónico. En el sidebar, el expander **🔗 Nombres unificados** muestra cada unificación y permite corregirla a mano (editar "Unificado a"); las correcciones se aplican al instante sin recargar. Puedes exportar el mapa como `names.csv` (columnas `Variant,Canonical`) y colocarlo en la carpeta del torneo o subirlo al perfil de nube — se aplica como fuente autoritativa en cada carga. Jugadores distintos con apellido igual ("Luis Perez" vs "Jose Perez") **no** se mezclan; hay test de regresión que lo garantiza.

Dashboard de análisis de datos TrackMan de béisbol construido con Streamlit, con diseño inspirado en Baseball Savant.

## Cómo correrlo

```bash
pip install -r requirements.txt
streamlit run trackman_app.py
```

## Fuentes de datos

**☁️ Perfiles (recomendado para equipos)** — almacenamiento compartido en la nube (Supabase Storage). Cualquier usuario del app puede: entrar a un perfil y ver todo lo que otros subieron, subir sus propios CSVs a ese perfil, o crear un perfil nuevo (se crea al subir su primer archivo). Los archivos no se pueden borrar ni sobreescribir desde el app (los duplicados se renombran con timestamp). Al subir un archivo, el app se actualiza para todos. Funciona en Streamlit Cloud y local. Si un perfil incluye un `regions.csv`, se carga como mapa de regiones.

Configuración: ya viene lista (URL y llave pública embebidas). Para usar otro proyecto Supabase, define `SUPABASE_URL` y `SUPABASE_KEY` en los secrets de Streamlit.

**⬆️ Upload CSVs** — sube uno o varios CSVs de TrackMan. El app los une, limpia y deduplica nombres de jugadores automáticamente.

**🏆 Carpeta local** — apunta el app a una carpeta de la computadora **donde corre el app**. Cada subcarpeta es un torneo. Nota: en Streamlit Cloud este modo no ve las carpetas de tu Mac — para compartir entre usuarios usa ☁️ Perfiles.

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

## Módulo de trayectorias (`trajectory/`)

Paquete independiente con motor físico de trayectorias release→plato, validación de rangos físicos, analítica (movement profile, release consistency, tendencias velo/spin) y API Flask documentada para integraciones externas. Ver `trajectory/README.md`. En el app: modo **🎯 Trayectorias 3D** con vista animada detrás del catcher (play/pausa + slider de frames), superposición de pitches, comparación de dos pitchers lado a lado, heatmaps por tipo y conteo, break chart, consistencia de release y tendencias por outing. Export: HTML interactivo y GIF vista-catcher. Tests: `pytest trajectory/tests/` (18 tests).

## Changelog v4.14

- 🃏 **Tarjetas en toda la app.** El look de tarjetas (`viz_card`: etiqueta mono + título +
  descripción, en `st.container(border=True)`) que estrenó Hitting ahora envuelve también **Pitching**
  (Summary → "ARSENAL — STUFF"/"DISCIPLINA", Location → "UBICACIÓN"/"POR TIPO DE PITCHEO",
  Trends → "TENDENCIA DE VELOCIDAD"/"USO POR CONTEO", "WHIFF% / CSW% POR ZONA"), **League**
  ("PROMEDIOS DE LIGA — PITCHING/— HITTING") y **Top Plays** ("LEADERBOARD" y "TARJETA PARA REDES").
- ✨ **App visualmente consistente**: se reemplazaron los encabezados `<div class="sh">` sueltos por
  la cabecera de tarjeta. Solo presentación — sin cambios de analítica, gráficos ni tema.

## Changelog v4.13

- 🎨 **Tema fijado a claro** (`.streamlit/config.toml`): la app ya no sigue el modo del sistema del
  visitante (que descuadraba los gráficos y el CSS en modo oscuro). Producción se ve siempre como el diseño.
- 🃏 **Presentación de Hitting en tarjetas**: helper `viz_card` (`st.container(border=True)` + CSS)
  envuelve cada gráfico/tabla con etiqueta + título + descripción (estilo preview).
- 🗺️ **Spray Pro con fondo claro** y el panel **BATTED BALL PROFILE** movido a un lado (HTML), ya no
  encima de los batazos — el campo queda limpio.

## Changelog v4.12

- 🏏 **Modo Hitting al nivel de Pitching.** Analítica extraída a `core/hitting.py` (pura) y gráficos
  a `viz/hitting.py` (**Plotly interactivo**): EV/LA distributions, EV×LA hit-quality map, damage
  zone, rolling EV — con hover/zoom.
- 🗺️ **Spray chart broadcast** (`viz/spray_render.py`): campo **top-down de día foto-realista**
  (pasto con franjas de corte, tierra, warning track, barda, bases) con dos toggles — **Pro**
  (matplotlib foto-realista) / **Interactivo** (Plotly con hover) y **Exit Velocity** / **Resultado**.
  Panel BATTED BALL PROFILE (Avg/Max EV, LA, HH%, Barrel%, wOBA) al lado.
- 🖨️ PDF de Hitting unificado a Plotly (vía kaleido). Se retiraron los gráficos matplotlib viejos.

## Changelog v4.11

- 🌃 **Modo Trayectorias 3D con look "Statcast broadcast" de noche.** Escena realista
  (matplotlib en perspectiva catcher): campo con franjas de corte, montículo, líneas de foul,
  zona 3×3 y **pelotas reales con costuras**. Fondo oscuro con las cintas/pelotas iluminadas.
- 🧾 **Panel PITCH ARSENAL fijo** a la izquierda en todas las vistas (tipo · velo · rpm/IVB/HB).
- 🎯 Vista **Pitches Thrown**: pelotas ubicadas en la zona con anillo de color por tipo y
  etiqueta de resultado (K/Out/1B/BB/HR).
- 🎞️ **GIF slow-mo nocturno** con el panel al lado durante toda la animación (ya no una tarjeta
  final). Animación, Pitches Thrown y GIF comparten el mismo motor realista de noche.
- 🧹 Se retiró el intento previo en Plotly (`trajectory/scene3d.py`) en favor del render realista.

## Changelog v4.9

- 🧱 Refactor "híbrido por fases": analítica de Pitching extraída a paquetes limpios
  `core/` (métricas puras) y `viz/` (figuras Plotly) — deja el terreno listo para un
  frontend futuro sin reescribir lógica.
- 🎯 Modo **Pitching interactivo**: los 6 gráficos migrados a Plotly (hover, zoom).
- 🆕 **Panel de Arsenal "Stuff"** en Summary: plot de movimiento interactivo (burbuja por
  tipo, tamaño = uso, hover con velo/spin/whiff/CSW) + tabla de arsenal con **CSW%**.
- 🖨️ PDF de pitching unificado sobre Plotly (vía `kaleido`, con degradación elegante).
- Nueva dependencia: `kaleido`.

## Changelog v4.4

- 🎯 Modo **Trayectorias 3D** (Plotly) con animación, scrubbing, overlay múltiple y comparación de pitchers
- Paquete `trajectory/`: motor físico (modos kinemático 9P e inferido), VAA/HAA, spin efficiency estimada, validación de rangos físicos con reporte, API Flask con 5 endpoints documentados, 18 tests
- Schema: soporte paquete 9P (`x0..az0`), `VertBreak`, `PitchUID`, aliases `ReleaseHeight/ReleaseSide/pitcher_id/batter_id`
- Nuevas dependencias: `plotly`, `pillow` (GIF); `flask` solo si usas la API

## Changelog v4.3

- ☁️ **Perfiles en la nube** (Supabase Storage): perfiles compartidos multi-usuario — todos ven lo subido en un perfil y pueden subir lo suyo; auto-refresh al subir; sin borrados ni sobreescrituras; `regions.csv` por perfil
- Backend: bucket `perfiles` con RLS (lectura pública + subida solo-CSV)
- Nueva dependencia: `supabase`

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

# Iteración 3 — Look "Statcast 3D" para el modo Trayectorias (día, catcher view)

**Fecha:** 2026-07-15
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Modo **🎯 Trayectorias 3D** (`trajectory/`).

## Contexto y motivación

El founder quiere que el modo 3D se vea como las transmisiones **Statcast 3D (powered by Google
Cloud)** de MLB. Guía visual: 5 fotos de una transmisión (All-Star 2026, Citizens Bank Park) en
`~/Downloads` (IMG_7649-7652 = "Pitch Arsenal" con cintas de trayectoria; IMG_2768 = "Pitches
Thrown" con pelotas ubicadas). El 3D actual (v4.8, `trajectory/streamlit_view.py`) ya tiene los
ingredientes (cintas de color, zona translúcida con grid, pelota con anillo, cámara catcher,
animación) pero en **escena nocturna oscura y plana**; la referencia es **día**: césped verde,
tierra en el home, cielo cálido, materiales glossy.

Decisión de plataforma (aprobada): **restyle Plotly al máximo** — no WebGL en esta iteración.
Alcance (aprobado): **ambas** — restyle de la animación **y** la vista "Pitches Thrown". Fondo
(aprobado): **híbrido** — campo (césped + tierra) + cielo suave, sin gradas.

## Requisitos críticos (énfasis del founder)

1. **Catcher view obligatorio.** La cámara va **detrás del plato** (extremo de y bajo, donde está
   el cátcher) mirando **hacia el pitcher** (+y). La zona queda en primer plano y el release/campo
   al fondo, como en las fotos. Coordenadas del engine: release ≈ y=54 ft, frente del plato =
   `PLATE_Y`=17/12≈1.417 ft; x = horizontal, z = altura.
2. **Trayectoria correcta.** La cinta debe trazar el **path físico real** de `compute_pitch_path`
   (modo kinemático 9P o inferido). El release en su altura/lado correctos, con el **break real**,
   terminando en la **ubicación real** del plato (`PlateLocSide`/`PlateLocHeight`). El restyle y la
   relación de aspecto de la escena **no deben distorsionar** la geometría — el arco/break debe
   leerse correctamente desde el catcher view (revisar `aspectratio`; la actual y=3.1 comprime la
   profundidad y aplana el arco — ajustar hasta que el vuelo se lea bien).

## Arquitectura

Nuevo módulo **`trajectory/scene3d.py`** — constructores Plotly **puros** (sin Streamlit),
testables, reutilizables por la animación y por la vista de ubicación:

```
trajectory/
  scene3d.py         # NUEVO: escena de campo + cintas + pelotas + 2 figuras
  streamlit_view.py  # UI delgada: llama a scene3d y arma los controles Streamlit
  engine.py          # (sin cambios) compute_pitch_path, pitch_metrics, PLATE_Y
```

`scene3d.py` reusa `STATCAST_COLORS`/`_pt_color` y `compute_pitch_path`/`pitch_metrics` de
`trajectory`. `streamlit_view.py` importa de `scene3d` y conserva la UI (selector de pitcher,
pitches, play/pausa, export). Regla: `scene3d.py` **no** importa `streamlit`.

### Interfaces de `scene3d.py`
- `field_scene_traces() -> list[go.BaseTraceType]` — escena diurna: césped, tierra del home, plano
  de cielo con degradado, plato, líneas de foul, goma del pitcher, y la caja de zona 3×3.
- `pitch_ribbon_traces(path, color, label) -> list` — cinta glossy por capas (glow + cuerpo +
  núcleo brillante) para un `path` (lista de `(x,y,z,t)`).
- `ball_marker_traces(x, y, z, color, label="", core="#ffffff") -> list` — pelota blanca con halo
  de color (anillo semitransparente + núcleo blanco), opcional etiqueta de texto.
- `build_pitch_animation(rows, n_points=50, title="") -> (go.Figure|None, list[metas])` — la
  animación restyled (reemplaza a `build_3d_figure`), con catcher view y controles.
- `pitches_thrown_figure(rows, title="") -> go.Figure|None` — vista de pelotas ubicadas.
- `catcher_scene_layout(title="") -> dict` — layout compartido: `scene` con `camera` catcher,
  `aspectratio` calibrado, ejes ocultos, `bgcolor`, `paper_bgcolor`.

## Escena diurna "híbrida" (`field_scene_traces`)

Reemplaza la escena nocturna (`SCENE_BG="#0b1523"`, piso `#152438`) por:
- **Césped:** `Mesh3d` verde (`#4a7c3f`) z=0 desde el home (y≈-2) hacia el campo (y≈70), con
  `lighting`/`lightposition` para un sheen suave.
- **Tierra del home:** polígono `Mesh3d` tan/marrón (`#b06a43`) alrededor del plato (área del
  home/círculo de bateo) sobre el césped; goma del pitcher en tierra al fondo.
- **Cielo:** plano vertical `Mesh3d` lejano (y≈72), ancho en x y alto en z, con `vertexcolor` en
  degradado horizonte→cenit (durazno `#f3d9c0` abajo → azul suave `#9cc3e0` arriba). Es la forma de
  evocar el cielo cálido (el `bgcolor` de la escena no admite degradado).
- **Zona 3×3:** panel translúcido blanco + marco brillante + grid interno (se conserva de v4.8,
  un poco más brillante).
- **Plato + líneas de foul + goma** (se conservan, en tonos claros).
- `scene.bgcolor` y `paper_bgcolor` = azul cielo suave (`#bcd7ea`) para que los bordes fundan con
  el plano de cielo.

## Cintas + pelotas (restyle de la animación — ref IMG_7649-7652)

- **Cintas glossy por capas** (en `pitch_ribbon_traces`): (a) glow ancho baja opacidad, (b) cuerpo
  de color (Statcast) opacidad alta, (c) **núcleo brillante fino** (tinte claro del color) para el
  highlight glossy. Todas siguen los mismos puntos de `path` (geometría real).
- **Pelota con halo** (en `ball_marker_traces`): anillo de color grande semitransparente + núcleo
  blanco, en el cruce del plato — como la foto. También en release una bolita blanca pequeña.
- **Animación:** se conserva la mecánica actual (frames de estela + pelota que avanza por el path,
  play/pausa + slider). La pelota animada viaja por el path real desde release hasta el plato.

## Vista "Pitches Thrown" 3D (nueva — ref IMG_2768)

`pitches_thrown_figure(rows)`:
- Para cada pitcheo con `PlateLocSide`/`PlateLocHeight`, una **pelota blanca con anillo de color por
  tipo** ubicada en `(x=PlateLocSide, y=PLATE_Y, z=PlateLocHeight)` sobre la caja de zona.
- **Etiqueta de resultado** flotando encima de la pelota: de `PlayResult` cuando es terminal
  (1B/2B/3B/HR/Out/K/BB/HBP…); si no hay `PlayResult`, sin etiqueta. Texto pequeño claro.
- Misma escena de campo + catcher view. Sin animación (es una vista estática).
- Hover: tipo de pitcheo, velo, resultado.
- Degrada a figura vacía con mensaje si faltan columnas de ubicación.

## UI (`render_trajectory_mode` en `streamlit_view.py`)

Dentro del modo 🎯 Trayectorias 3D, la sección de visualización 3D ofrece dos sub-vistas
(radio/tabs): **"🎥 Animación"** (la restyled) y **"🎯 Pitches Thrown"** (la nueva). El resto de la
UI del modo (selector de pitcher, selección de pitches, heatmaps, break chart, release, tendencias,
export) se conserva. Los otros modos del app no se tocan.

## Verificación (clave — es un cambio de *look*)

La estética NO se valida solo con tests. Bucle de verificación visual:
1. Renderizar `build_pitch_animation` (frame representativo) y `pitches_thrown_figure` a **PNG vía
   kaleido** con un DataFrame realista.
2. **Comparar contra las fotos de referencia** (IMG_7649-7652, IMG_2768) — chequear: catcher view
   correcto, trayectoria/arco físico correcto (release alto y lejos → break → plato), césped/tierra/
   cielo diurnos, cintas glossy y pelotas con halo, zona 3×3 legible.
3. **Iterar** el styling (colores, cámara, `aspectratio`, gradiente de cielo, grosores/opacidades)
   hasta que evoque la transmisión.
4. Visto bueno final del founder viéndolo en el app corriendo.

## Testing

`trajectory/tests/test_scene3d.py` (smoke, pytest):
- `field_scene_traces()` devuelve una lista no vacía de traces Plotly.
- `build_pitch_animation(rows)` devuelve `(go.Figure, metas)` con rows sintéticos; `(None, [])` con
  rows vacíos.
- `pitches_thrown_figure(rows)` devuelve `go.Figure`; con df sin columnas de ubicación devuelve una
  figura vacía sin lanzar.
- `catcher_scene_layout()` incluye `scene.camera` (catcher view) y `aspectratio`.
- Los 19 tests existentes de `trajectory/` siguen pasando (sin regresión del engine/API/analytics).

## No-goals (YAGNI)
- Sin WebGL/three.js (posible iteración futura para fotorrealismo).
- Sin estadio con gradas ni multitud.
- Sin tocar otros modos (Pitching/Hitting/League/Top Plays) ni la analítica del engine.
- Sin fotorrealismo — el objetivo es "evocar" el look Statcast dentro de Plotly.

## Criterios de aceptación
- [ ] `trajectory/scene3d.py` creado, puro (sin streamlit), con smoke tests; `trajectory/` sin
      regresión (19 tests verdes + los nuevos).
- [ ] Escena diurna híbrida (césped + tierra + cielo degradado) reemplaza la nocturna.
- [ ] **Catcher view** correcto (cámara detrás del plato mirando al pitcher) — verificado en render.
- [ ] **Trayectoria física correcta** (release→break→plato) sin distorsión — verificado en render.
- [ ] Cintas glossy + pelotas con halo (animación) y vista "Pitches Thrown" con etiquetas de
      resultado, ambas con la escena nueva.
- [ ] Sub-vistas "Animación" / "Pitches Thrown" en la UI del modo 3D.
- [ ] Comparación render↔referencia hecha e iterada; visto bueno del founder en el app.

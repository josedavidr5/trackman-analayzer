# Look Statcast 3D — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. NOTE: Task 5 (visual tuning) requires viewing rendered PNGs against reference photos — that is controller/human work, not a code-only subagent task.

**Goal:** Reestilizar el modo 3D de trayectorias al look "Statcast 3D" (escena diurna, catcher view, cintas glossy, pelotas con halo) y añadir la vista "Pitches Thrown", en Plotly.

**Architecture:** Nuevo módulo puro `trajectory/scene3d.py` (constructores Plotly, sin Streamlit) usado por `trajectory/streamlit_view.py` (UI delgada). Reusa `compute_pitch_path`/`pitch_metrics`/`PLATE_Y` de `trajectory.engine`.

**Tech Stack:** Python, numpy, Plotly (Scatter3d/Mesh3d + frames), Streamlit, kaleido (render a PNG para verificación), pytest.

## Global Constraints

- `trajectory/scene3d.py` NO importa `streamlit`. Solo `numpy`/`plotly` y `trajectory.engine`.
- **Catcher view:** cámara detrás del plato (y bajo) mirando al pitcher (+y); zona en primer plano.
- **Trayectoria correcta:** las cintas trazan los puntos reales de `compute_pitch_path`; no distorsionar la geometría; `aspectratio` calibrado para que el arco/break se lea (la actual y=3.1 aplana).
- Coordenadas: x horizontal, y = distancia al frente del plato (`PLATE_Y`=17/12≈1.417; release≈54; goma=60.5), z altura.
- Colores por tipo: `STATCAST_COLORS` (Statcast/Savant).
- Tests desde la raíz con `.venv/bin/python -m pytest`. Rama: `iter3-3d-statcast-look`. Un commit por tarea.

---

### Task 1: `trajectory/scene3d.py` — escena diurna + layout catcher

**Files:**
- Create: `trajectory/scene3d.py`
- Create: `trajectory/tests/test_scene3d.py`

**Interfaces:**
- Consumes: `trajectory.engine.PLATE_Y`
- Produces: `pt_color(pt, idx=0) -> str`, `field_scene_traces() -> list`, `catcher_scene_layout(title="") -> dict`, y constantes `ZONE_X, ZONE_LO, ZONE_HI`.

- [ ] **Step 1: Crear `trajectory/scene3d.py` con la escena y el layout**

```python
"""trajectory.scene3d — constructores Plotly puros del look 'Statcast 3D'.
Sin Streamlit. Escena diurna (catcher view), cintas glossy y pelotas con halo."""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
from .engine import PLATE_Y

STATCAST_COLORS = {
    "4-Seam": "#D22D49", "Fastball": "#D22D49", "Four-Seam Fastball": "#D22D49",
    "2-Seam": "#DE6A04", "Sinker": "#FE9D00", "Cutter": "#933F2C", "Slider": "#C3BD0E",
    "Sweeper": "#DDB33A", "Curve": "#00D1ED", "Curveball": "#00D1ED",
    "Change": "#1DBE3A", "Changeup": "#1DBE3A", "Split": "#3BACAC",
    "Knuckleball": "#3C44CD", "Screwball": "#60DB33",
}
_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2"]

def pt_color(pt, idx=0):
    return STATCAST_COLORS.get(str(pt), _PALETTE[idx % len(_PALETTE)])

ZONE_X, ZONE_LO, ZONE_HI = 0.83, 1.5, 3.5
GRASS, DIRT = "#4a7c3f", "#b06a43"
SKY_LO, SKY_HI, BG = "#f3d9c0", "#9cc3e0", "#bcd7ea"

def _rgb(h):
    h = h.lstrip("#")
    return f"rgb({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)})"

def _lighten(hexc, f=0.55):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgb({int(r+(255-r)*f)},{int(g+(255-g)*f)},{int(b+(255-b)*f)})"

def field_scene_traces():
    """Escena diurna híbrida: cielo degradado, césped, tierra, zona 3×3, plato, foul, goma."""
    t = []
    # cielo: quad vertical lejano con degradado vertexcolor (horizonte→cenit)
    t.append(go.Mesh3d(
        x=[-42, 42, 42, -42], y=[71, 71, 71, 71], z=[0, 0, 17, 17],
        i=[0, 0], j=[1, 2], k=[2, 3],
        vertexcolor=[_rgb(SKY_LO), _rgb(SKY_LO), _rgb(SKY_HI), _rgb(SKY_HI)],
        hoverinfo="skip", showscale=False, lighting=dict(ambient=1.0, diffuse=0.0)))
    # césped
    t.append(go.Mesh3d(
        x=[-35, 35, 35, -35], y=[-2, -2, 70, 70], z=[0, 0, 0, 0], i=[0, 0], j=[1, 2], k=[2, 3],
        color=GRASS, hoverinfo="skip", showscale=False,
        lighting=dict(ambient=0.78, diffuse=0.5, specular=0.12),
        lightposition=dict(x=0, y=-30, z=60)))
    # tierra del home + montículo
    t.append(go.Mesh3d(x=[-8, 8, 8, -8], y=[-2, -2, 9, 9], z=[0.01] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3], color=DIRT, hoverinfo="skip", showscale=False))
    t.append(go.Mesh3d(x=[-6, 6, 6, -6], y=[54, 54, 64, 64], z=[0.01] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3], color=DIRT, opacity=0.92, hoverinfo="skip", showscale=False))
    # zona 3×3: panel + marco + grid
    y = PLATE_Y
    t.append(go.Mesh3d(x=[-ZONE_X, ZONE_X, ZONE_X, -ZONE_X], y=[y] * 4,
        z=[ZONE_LO, ZONE_LO, ZONE_HI, ZONE_HI], i=[0, 0], j=[1, 2], k=[2, 3],
        color="#ffffff", opacity=0.12, hoverinfo="skip", showscale=False))
    t.append(go.Scatter3d(x=[-ZONE_X, ZONE_X, ZONE_X, -ZONE_X, -ZONE_X], y=[y] * 5,
        z=[ZONE_LO, ZONE_LO, ZONE_HI, ZONE_HI, ZONE_LO], mode="lines",
        line=dict(color="#ffffff", width=6), opacity=0.95, showlegend=False, hoverinfo="skip"))
    for f in (1 / 3, 2 / 3):
        gx = -ZONE_X + 2 * ZONE_X * f
        gz = ZONE_LO + (ZONE_HI - ZONE_LO) * f
        t.append(go.Scatter3d(x=[gx, gx], y=[y, y], z=[ZONE_LO, ZONE_HI], mode="lines",
            line=dict(color="#ffffff", width=2), opacity=0.35, showlegend=False, hoverinfo="skip"))
        t.append(go.Scatter3d(x=[-ZONE_X, ZONE_X], y=[y, y], z=[gz, gz], mode="lines",
            line=dict(color="#ffffff", width=2), opacity=0.35, showlegend=False, hoverinfo="skip"))
    # plato, foul, goma
    t.append(go.Scatter3d(x=[-0.71, 0.71, 0.71, 0, -0.71, -0.71], y=[y, y, 0.4, 0.1, 0.4, y],
        z=[0.02] * 6, mode="lines", line=dict(color="#ffffff", width=5), opacity=0.95,
        showlegend=False, hoverinfo="skip"))
    for sgn in (1, -1):
        t.append(go.Scatter3d(x=[sgn * 0.71, sgn * 20.0], y=[1.4, 22.0], z=[0.02, 0.02],
            mode="lines", line=dict(color="#ffffff", width=3), opacity=0.5,
            showlegend=False, hoverinfo="skip"))
    t.append(go.Scatter3d(x=[-0.9, 0.9], y=[60.5, 60.5], z=[0.83, 0.83], mode="lines",
        line=dict(color="#f2f2f2", width=6), opacity=0.8, showlegend=False, hoverinfo="skip"))
    return t

def catcher_scene_layout(title=""):
    """Layout compartido con cámara catcher (detrás del plato → pitcher) y aspecto calibrado."""
    ax = dict(visible=False, showgrid=False, zeroline=False,
              showbackground=False, showticklabels=False)
    return dict(
        title=dict(text=title, font=dict(color="#12324a", size=15), x=0.03),
        height=640, margin=dict(l=0, r=0, t=44, b=0), paper_bgcolor=BG, showlegend=False,
        scene=dict(
            bgcolor=BG,
            xaxis={**ax, "range": [-6, 6]},
            yaxis={**ax, "range": [66, -2.5]},   # reversed: release atrás, plato adelante
            zaxis={**ax, "range": [-0.1, 11]},
            aspectmode="manual", aspectratio=dict(x=1, y=2.2, z=0.9),
            camera=dict(eye=dict(x=0.0, y=-1.95, z=0.42),
                        center=dict(x=0, y=-0.20, z=-0.05),
                        up=dict(x=0, y=0, z=1))))
```

- [ ] **Step 2: Escribir smoke tests en `trajectory/tests/test_scene3d.py`**

```python
import plotly.graph_objects as go
from trajectory import scene3d

def test_field_scene_traces_nonempty():
    tr = scene3d.field_scene_traces()
    assert isinstance(tr, list) and len(tr) >= 8
    assert all(isinstance(x, go.graph_objs._scatter3d.Scatter3d) or
               isinstance(x, go.graph_objs._mesh3d.Mesh3d) for x in tr)

def test_catcher_layout_has_camera_and_aspect():
    lay = scene3d.catcher_scene_layout("t")
    assert "camera" in lay["scene"]
    assert lay["scene"]["aspectratio"]["y"] != lay["scene"]["aspectratio"]["x"]
    # catcher view: eye detrás del plato (y negativo en coords normalizadas)
    assert lay["scene"]["camera"]["eye"]["y"] < 0

def test_pt_color_known_and_fallback():
    assert scene3d.pt_color("Slider") == "#C3BD0E"
    assert scene3d.pt_color("X", 0) == "#1f77b4"
```

- [ ] **Step 3: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest trajectory/tests/test_scene3d.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add trajectory/scene3d.py trajectory/tests/test_scene3d.py
git commit -m "feat: trajectory/scene3d — escena diurna Statcast + layout catcher view"
```

---

### Task 2: `scene3d` — cintas glossy, pelotas con halo, `build_pitch_animation`

**Files:**
- Modify: `trajectory/scene3d.py`
- Modify: `trajectory/tests/test_scene3d.py`

**Interfaces:**
- Consumes: `trajectory.engine.compute_pitch_path`, `pitch_metrics`; `field_scene_traces`, `catcher_scene_layout`, `pt_color`.
- Produces: `pitch_ribbon_traces(path, color, label="") -> list`, `ball_marker_traces(x,y,z,color,label="",core="#ffffff",opacity=1.0) -> list`, `build_pitch_animation(rows, n_points=50, title="") -> (go.Figure|None, list)`.

- [ ] **Step 1: Añadir los constructores de cinta y pelota + la animación a `trajectory/scene3d.py`**

```python
def pitch_ribbon_traces(path, color, label=""):
    """Cinta glossy por capas (glow + cuerpo + núcleo brillante) sobre los puntos reales."""
    xs = [p[0] for p in path]; ys = [p[1] for p in path]; zs = [p[2] for p in path]
    body = go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=color, width=9),
                        opacity=0.98, name=label)
    if label:
        body.update(hovertemplate=label + "<extra></extra>")
    else:
        body.update(hoverinfo="skip", showlegend=False)
    return [
        go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=color, width=20),
                     opacity=0.16, showlegend=False, hoverinfo="skip"),
        body,
        go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color=_lighten(color), width=3),
                     opacity=0.9, showlegend=False, hoverinfo="skip"),
    ]

def ball_marker_traces(x, y, z, color, label="", core="#ffffff", opacity=1.0):
    """Pelota blanca con halo de color (anillo semitransparente + núcleo). Etiqueta opcional."""
    halo = go.Scatter3d(x=[x], y=[y], z=[z], mode="markers",
                        marker=dict(size=17, color=color, opacity=0.45 * opacity),
                        showlegend=False, hoverinfo="skip")
    corem = go.Scatter3d(x=[x], y=[y], z=[z], mode="markers",
                         marker=dict(size=9, color=core, opacity=opacity,
                                     line=dict(color=color, width=2)), showlegend=False)
    if label:
        corem.update(hovertemplate=label + "<extra></extra>")
    else:
        corem.update(hoverinfo="skip")
    out = [halo, corem]
    if label:
        out.append(go.Scatter3d(x=[x], y=[y], z=[z + 0.5], mode="text", text=[label],
                                textfont=dict(color="#12324a", size=11),
                                showlegend=False, hoverinfo="skip"))
    return out

def _pitch_label(row):
    import pandas as pd
    v = row.get("RelSpeed"); s = row.get("SpinRate")
    bits = [str(row.get("TaggedPitchType", "?"))]
    if pd.notna(v): bits.append(f"{float(v):.1f} mph")
    if pd.notna(s): bits.append(f"{float(s):.0f} rpm")
    return " · ".join(bits)

def build_pitch_animation(rows, n_points=50, title=""):
    """Animación 3D restyled (catcher view): cintas glossy + pelota con halo por el path real."""
    paths, labels, colors, metas = [], [], [], []
    for i, (_, r) in enumerate(rows.iterrows()):
        try:
            paths.append(compute_pitch_path(r, n_points=n_points))
        except ValueError:
            continue
        labels.append(_pitch_label(r)); colors.append(pt_color(r.get("TaggedPitchType"), i))
        metas.append(pitch_metrics(r))
    if not paths:
        return None, []
    base = list(field_scene_traces())
    for path, lab, col in zip(paths, labels, colors):
        base += pitch_ribbon_traces(path, col, lab)
        base += ball_marker_traces(path[0][0], path[0][1], path[0][2], col, core="#ffffff")  # release
        base += ball_marker_traces(path[-1][0], path[-1][1], path[-1][2], col, label="")      # plato
    # traces animados (invisibles al inicio): estela + halo + núcleo por pitcheo
    anim_start = len(base)
    for path, col in zip(paths, colors):
        p0 = path[0]
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="lines",
            line=dict(color="#ffffff", width=4), opacity=0.0, showlegend=False, hoverinfo="skip"))
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="markers",
            marker=dict(size=15, color=col, opacity=0.0), showlegend=False, hoverinfo="skip"))
        base.append(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode="markers",
            marker=dict(size=9, color="#ffffff", opacity=0.0), showlegend=False, hoverinfo="skip"))
    frames = []
    for k in range(n_points):
        data = []
        for path, col in zip(paths, colors):
            seg = path[:k + 1]
            xs = [p[0] for p in seg]; ys = [p[1] for p in seg]; zs = [p[2] for p in seg]
            data.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                line=dict(color="#ffffff", width=3), opacity=0.6))
            data.append(go.Scatter3d(x=[xs[-1]], y=[ys[-1]], z=[zs[-1]], mode="markers",
                marker=dict(size=15, color=col, opacity=0.5)))
            data.append(go.Scatter3d(x=[xs[-1]], y=[ys[-1]], z=[zs[-1]], mode="markers",
                marker=dict(size=9, color="#ffffff", opacity=1.0)))
        frames.append(go.Frame(data=data,
            traces=list(range(anim_start, anim_start + 3 * len(paths))), name=str(k)))
    fig = go.Figure(data=base, frames=frames)
    steps = [dict(method="animate", label=f"{k}",
                  args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}])
             for k in range(n_points)]
    fig.update_layout(**catcher_scene_layout(title))
    fig.update_layout(
        updatemenus=[dict(type="buttons", showactive=False, y=0.02, x=0.02, xanchor="left",
            bgcolor="rgba(255,255,255,0.25)", font=dict(color="#12324a"),
            bordercolor="rgba(0,0,0,0.2)", buttons=[
                dict(label="▶ Play", method="animate",
                     args=[None, {"frame": {"duration": 28, "redraw": True},
                                  "fromcurrent": True, "transition": {"duration": 0}}]),
                dict(label="⏸", method="animate",
                     args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}]),
            ])],
        sliders=[dict(steps=steps, active=0, y=0.0, x=0.18, len=0.78,
                      currentvalue=dict(prefix="frame ", font=dict(color="#12324a")),
                      font=dict(color="#12324a"), bgcolor="rgba(255,255,255,0.4)",
                      bordercolor="rgba(0,0,0,0)")])
    return fig, metas
```

Añadir al import de `trajectory/scene3d.py` (arriba): `from .engine import compute_pitch_path, pitch_metrics, PLATE_Y` (extender el import existente).

- [ ] **Step 2: Añadir smoke tests**

```python
import numpy as np, pandas as pd
from trajectory import scene3d as s3

def _rows():
    return pd.DataFrame({
        "TaggedPitchType": ["Fastball", "Slider"],
        "RelSpeed": [94.0, 84.0], "SpinRate": [2300, 2500],
        "RelSide": [-1.8, -1.7], "RelHeight": [5.9, 5.8], "Extension": [6.5, 6.4],
        "InducedVertBreak": [16.0, 2.0], "HorzBreak": [-8.0, 7.0],
        "PlateLocSide": [0.2, -0.3], "PlateLocHeight": [2.8, 2.1],
    })

def test_build_pitch_animation_ok_and_empty():
    fig, metas = s3.build_pitch_animation(_rows(), n_points=20, title="P")
    import plotly.graph_objects as go
    assert isinstance(fig, go.Figure) and len(fig.frames) == 20 and len(metas) == 2
    fig2, metas2 = s3.build_pitch_animation(pd.DataFrame({"TaggedPitchType": []}))
    assert fig2 is None and metas2 == []

def test_ribbon_and_ball_trace_counts():
    path = [(0, 54, 6, 0.0), (0.1, 30, 4, 0.2), (0.2, 1.42, 2.8, 0.4)]
    assert len(s3.pitch_ribbon_traces(path, "#D22D49", "FB")) == 3
    assert len(s3.ball_marker_traces(0, 1.42, 2.8, "#D22D49", label="K")) == 3
    assert len(s3.ball_marker_traces(0, 1.42, 2.8, "#D22D49")) == 2
```

Note: si `compute_pitch_path` requiere nombres de columnas distintos (p.ej. `ReleaseHeight`/`ReleaseSide`), ajustar `_rows()` a lo que el engine espera — revisar `trajectory/engine.py` y sus aliases antes de escribir el test.

- [ ] **Step 3: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest trajectory/tests/test_scene3d.py -v`
Expected: todos pasan.

- [ ] **Step 4: Commit**

```bash
git add trajectory/scene3d.py trajectory/tests/test_scene3d.py
git commit -m "feat: scene3d cintas glossy + pelotas con halo + build_pitch_animation (catcher view)"
```

---

### Task 3: `scene3d.pitches_thrown_figure` — vista de pelotas ubicadas

**Files:**
- Modify: `trajectory/scene3d.py`
- Modify: `trajectory/tests/test_scene3d.py`

**Interfaces:**
- Produces: `pitches_thrown_figure(rows, title="") -> go.Figure|None`.

- [ ] **Step 1: Añadir la función a `trajectory/scene3d.py`**

```python
_TERMINAL = {"1B", "2B", "3B", "HR", "Out", "K", "BB", "HBP", "FC", "Error", "SacFly", "SacBunt"}

def pitches_thrown_figure(rows, title=""):
    """Vista 3D de pelotas ubicadas en la zona, anillo de color por tipo, etiqueta de resultado."""
    if not {"PlateLocSide", "PlateLocHeight"}.issubset(rows.columns):
        fig = go.Figure(data=field_scene_traces())
        fig.add_annotation(text="Sin datos de ubicación", showarrow=False)
        fig.update_layout(**catcher_scene_layout(title))
        return fig
    import pandas as pd
    loc = rows.dropna(subset=["PlateLocSide", "PlateLocHeight"])
    data = list(field_scene_traces())
    for i, (_, r) in enumerate(loc.iterrows()):
        col = pt_color(r.get("TaggedPitchType"), i)
        res = str(r.get("PlayResult", "")) if pd.notna(r.get("PlayResult", np.nan)) else ""
        label = res if res in _TERMINAL else ""
        hov = _pitch_label(r) + (f" · {res}" if label else "")
        data += ball_marker_traces(float(r["PlateLocSide"]), PLATE_Y, float(r["PlateLocHeight"]),
                                   col, label=label)
        # hover en el núcleo: reemplazar el último core sin label — más simple: añadir punto hover
    fig = go.Figure(data=data)
    fig.update_layout(**catcher_scene_layout(title or "Pitches Thrown"))
    return fig
```

- [ ] **Step 2: Añadir smoke tests**

```python
def test_pitches_thrown_ok_and_missing_cols():
    import plotly.graph_objects as go
    df = pd.DataFrame({
        "TaggedPitchType": ["Fastball", "Slider", "Sinker"],
        "PlateLocSide": [0.1, -0.4, 0.6], "PlateLocHeight": [2.6, 2.0, 3.1],
        "RelSpeed": [94, 84, 92], "PlayResult": ["K", "Out", "1B"],
    })
    assert isinstance(s3.pitches_thrown_figure(df, "t"), go.Figure)
    # sin columnas de ubicación → figura (no lanza)
    assert isinstance(s3.pitches_thrown_figure(pd.DataFrame({"TaggedPitchType": ["FB"]})), go.Figure)
```

- [ ] **Step 3: Correr los tests — deben pasar**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -m pytest trajectory/tests/test_scene3d.py -v`
Expected: todos pasan.

- [ ] **Step 4: Commit**

```bash
git add trajectory/scene3d.py trajectory/tests/test_scene3d.py
git commit -m "feat: scene3d pitches_thrown_figure — pelotas ubicadas con resultado"
```

---

### Task 4: Wire en `streamlit_view.py` — sub-vistas Animación / Pitches Thrown

**Files:**
- Modify: `trajectory/streamlit_view.py`

**Interfaces:**
- Consumes: `trajectory.scene3d.{build_pitch_animation, pitches_thrown_figure}`.

- [ ] **Step 1: Importar de `scene3d` y delegar la construcción de la animación**

En `trajectory/streamlit_view.py`, añadir cerca de los imports:
```python
from . import scene3d
```
Reemplazar la función local `build_3d_figure(...)` por un delegado (para no tocar sus call-sites):
```python
def build_3d_figure(rows, n_points=50, title=""):
    return scene3d.build_pitch_animation(rows, n_points=n_points, title=title)
```
(Las funciones locales `_zone_traces`, `SCENE_BG`, `_pt_color`, `_pitch_label`, `N_ZONE_TRACES` que solo servían a la vieja `build_3d_figure` quedan sin uso; borrarlas si ningún otro call-site las usa — verificar con grep antes de borrar.)

- [ ] **Step 2: Añadir el selector de sub-vista donde se renderiza la animación**

Localizar en `render_trajectory_mode` el punto donde hoy se llama `build_3d_figure(...)` y se hace `st.plotly_chart(...)` para la animación. Envolverlo con un radio de sub-vista:
```python
        sub = st.radio("Vista 3D", ["🎥 Animación", "🎯 Pitches Thrown"],
                       key="traj3d_subview", horizontal=True)
        if sub == "🎥 Animación":
            fig3d, metas = build_3d_figure(sub_rows, n_points=n_pts, title=titulo)
            if fig3d is not None:
                st.plotly_chart(fig3d, use_container_width=True)
            else:
                st.info("No se pudo reconstruir la trayectoria de los pitches seleccionados.")
        else:
            st.plotly_chart(scene3d.pitches_thrown_figure(sub_rows, title=titulo),
                            use_container_width=True)
```
(Ajustar `sub_rows`, `n_pts`, `titulo` a los nombres reales que ya existen en esa parte de `render_trajectory_mode` — leer el bloque actual antes de editar.)

- [ ] **Step 3: Verificar sintaxis + import smoke + suite de trajectory**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trajectory/streamlit_view.py').read()); print('syntax ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest trajectory/tests/ core/tests/ viz/tests/ -q`
Expected: "syntax ok", "import ok", y toda la suite pasa (19 trajectory + nuevos scene3d + core + viz).

- [ ] **Step 4: Commit**

```bash
git add trajectory/streamlit_view.py
git commit -m "feat: sub-vistas Animación / Pitches Thrown en el modo 3D"
```

---

### Task 5: Verificación visual + tuning (controller/founder — no code-only)

**Files:** Modify `trajectory/scene3d.py` (ajustes de estilo iterativos)

Esta tarea es el bucle visual: renderizar a PNG, comparar con las fotos de referencia
(`~/Downloads` IMG_7649-7652, IMG_2768) e iterar. Requiere ver imágenes → la hace el controller.

- [ ] **Step 1: Script de render a PNG** — crear un DataFrame realista (varios tipos con break) y renderizar ambas figuras:

```bash
cd /Users/joseramirez/trackman-analayzer && .venv/bin/python - <<'PY'
import numpy as np, pandas as pd
from trajectory import scene3d as s3
rows = pd.DataFrame({
  "TaggedPitchType":["Four-Seam","Changeup","Sinker","Curveball","Cutter","Slider"],
  "RelSpeed":[93.9,85.6,92.5,79.1,90.6,87.1],
  "SpinRate":[2300,1700,2100,2600,2400,2500],
  "RelSide":[-1.8]*6,"RelHeight":[5.9]*6,"Extension":[6.5]*6,
  "InducedVertBreak":[16,8,10,-8,6,2],"HorzBreak":[-8,-12,-10,6,2,7],
  "PlateLocSide":[0.2,-0.3,0.4,-0.1,0.0,0.3],
  "PlateLocHeight":[3.0,2.2,2.4,1.8,2.6,2.0],
  "PlayResult":["K","Out","1B","BB","Out","K"],
})
fig,_ = s3.build_pitch_animation(rows, n_points=30, title="Test")
fig.write_image("/tmp/_anim.png", width=1100, height=680, scale=2)
s3.pitches_thrown_figure(rows,"Pitches Thrown").write_image("/tmp/_thrown.png", width=1100, height=680, scale=2)
print("ok")
PY
```
(Ajustar nombres de columnas de release/break a lo que `compute_pitch_path` espera, verificado en la Task 2.)

- [ ] **Step 2: Ver los PNGs y comparar con la referencia.** Chequear: (a) **catcher view** — se ve desde detrás del plato hacia el pitcher, zona en primer plano; (b) **trayectoria** — release alto/lejos → break → plato, arco no aplanado; (c) día (césped/tierra/cielo); (d) cintas glossy y pelotas con halo; (e) grid 3×3 legible; (f) etiquetas de resultado en Pitches Thrown.

- [ ] **Step 3: Iterar** los parámetros en `scene3d.py` hasta que evoque la referencia: `catcher_scene_layout` (`camera.eye/center`, `aspectratio`), colores/opacidades de césped/tierra/cielo, grosores de cinta, tamaños de halo. Re-render y re-ver tras cada ajuste. Commit cuando esté bien:
```bash
git add trajectory/scene3d.py && git commit -m "style: calibrar catcher view, aspecto y materiales del 3D vs referencia"
```

- [ ] **Step 4: Visto bueno del founder** corriendo el app: `.venv/bin/streamlit run trackman_app.py` → 🎯 Trayectorias 3D → probar Animación y Pitches Thrown.

---

## Self-Review

**1. Spec coverage:** `scene3d.py` puro (Task 1-3); escena diurna híbrida (Task 1); catcher view + aspect (Task 1, tuned Task 5); trayectoria real vía compute_pitch_path (Task 2); cintas glossy + halos (Task 2); Pitches Thrown con resultado (Task 3); sub-vistas UI (Task 4); verificación visual (Task 5); smoke tests (Task 1-3); sin regresión trajectory (Task 4). ✓

**2. Placeholder scan:** El código nuevo está completo. Los puntos "ajustar a nombres reales" (columnas del engine en Task 2/5; variables de `render_trajectory_mode` en Task 4) son verificaciones explícitas contra el código existente, no placeholders de lógica — cada uno dice qué revisar y dónde.

**3. Type consistency:** `build_pitch_animation` retorna `(fig|None, metas)` igual que la vieja `build_3d_figure`, y el delegado preserva la firma para los call-sites. `pitches_thrown_figure` retorna `go.Figure`. `pitch_ribbon_traces`/`ball_marker_traces` retornan listas de traces. ✓

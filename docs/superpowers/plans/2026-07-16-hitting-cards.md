# Presentación de Hitting (tarjetas) + tema fijado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development o superpowers:executing-plans. Steps con checkbox (`- [ ]`). La Task 3 (captura Playwright + comparación visual) requiere ver imágenes — es trabajo de controller.

**Goal:** Que el modo Hitting se vea como el preview aprobado: tema claro fijado + cada gráfico/tabla en una tarjeta con etiqueta/título/descripción.

**Architecture:** Fijar el tema de Streamlit (config.toml), agregar un helper `viz_card` (`st.container(border=True)` + CSS) y envolver todos los gráficos/tablas de `render_hitting`. Sin lógica nueva.

**Tech Stack:** Streamlit 1.59.2 (`st.container(border=True)` — verificado), CSS inline, Playwright (chromium, ya instalado) para la captura.

## Global Constraints

- Solo se toca **Hitting** + config de tema + helper/CSS compartido. No tocar Pitching/League/Top Plays/3D.
- Tema **claro** (Savant): primary `#1f77b4`, bg `#ffffff`, secondary `#fafafa`, text `#333333`.
- `trackman_app.py` usa **CRLF** — preservar al editar por script.
- Sin dark mode, sin cambiar analítica/gráficos/spray render.
- Verificación: `import trackman_app` OK + captura Playwright del modo Hitting + suite existente verde (70).

---

### Task 1: Tema fijado + helper `viz_card` + CSS

**Files:**
- Create: `.streamlit/config.toml`
- Modify: `trackman_app.py` (añadir CSS al bloque `<style>` en :153 y el helper `viz_card` junto a `csv_dl`/`fmt` ~:314)

- [ ] **Step 1: Crear `.streamlit/config.toml`**

```toml
[theme]
base = "light"
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#fafafa"
textColor = "#333333"
```

- [ ] **Step 2: Añadir el CSS de tarjeta al bloque `<style>` existente**

En `trackman_app.py`, dentro del `st.markdown("""<style>` (empieza en :153), añadir cerca de `.stat-badge`:

```css
.viz-eyebrow{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.62rem;
  letter-spacing:.18em;text-transform:uppercase;color:#1f77b4;font-weight:700;margin-bottom:2px}
.viz-title{font-size:1.05rem;font-weight:800;letter-spacing:-.01em;line-height:1.2;
  margin-bottom:3px;color:#222}
.viz-desc{font-size:.82rem;color:#5b6b78;line-height:1.45;margin-bottom:8px}
```
(Insertarlo como parte del string CSS; respetar que el archivo es CRLF.)

- [ ] **Step 3: Añadir el helper `viz_card`** (junto a `csv_dl`/`fmt`, ~:314)

```python
def viz_card(eyebrow, title, desc=""):
    """Container con borde + cabecera (etiqueta/título/descripción) estilo preview.
    Uso:  with viz_card("EYEBROW","Título","desc"): st.plotly_chart(fig, ...)"""
    c = st.container(border=True)
    with c:
        st.markdown(f'<div class="viz-eyebrow">{eyebrow}</div>'
                    f'<div class="viz-title">{title}</div>'
                    + (f'<div class="viz-desc">{desc}</div>' if desc else ""),
                    unsafe_allow_html=True)
    return c
```

- [ ] **Step 4: Verificar sintaxis + import**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('syntax ok')" && .venv/bin/python -c "import trackman_app; print('import ok')"`
Expected: "syntax ok", "import ok".

- [ ] **Step 5: Commit**

```bash
git add .streamlit/config.toml trackman_app.py
git commit -m "feat: tema claro fijado + helper viz_card + CSS de tarjeta"
```

---

### Task 2: Envolver los gráficos/tablas de Hitting en tarjetas

**Files:**
- Modify: `trackman_app.py` (`render_hitting`, tabs 1-5)

**Interfaces:**
- Consumes: `viz_card(eyebrow, title, desc="")` de la Task 1.

- [ ] **Step 1: Reemplazar el contenido de los tabs de `render_hitting`** (actual :1418-:1470) por la versión con tarjetas:

```python
    with tab1:
        monthly_df=build_hitting_monthly(bdf,lmeta)
        with viz_card("PROGRESIÓN MENSUAL","Mes a mes","EV/LA/distancia, HH%, Barrel%, K/BB, wOBA por mes."):
            if monthly_df.empty: st.info("No monthly data.")
            else:
                st.dataframe(monthly_df,use_container_width=True,hide_index=True)
                csv_dl(monthly_df,f"{selected}_monthly.csv")
        with viz_card("ROLLING EV","Tendencia de Exit Velocity","Media móvil de EV por batazo (cronológico)."):
            st.plotly_chart(vhit.rolling_ev(bdf,selected),use_container_width=True)
    with tab2:
        split_df=build_split_table(bdf,ev_hard=EV_HARD)
        with viz_card("SPLITS vs RHP/LHP","Rendimiento por mano del pitcher","EV, HH%, disciplina y wOBA vs derechos e izquierdos."):
            if split_df.empty: st.info("PitcherThrows column required.")
            else:
                st.dataframe(split_df,use_container_width=True,hide_index=True)
                csv_dl(split_df,f"{selected}_splits.csv")
        hands=bdf["PitcherThrows"].dropna().unique() if "PitcherThrows" in bdf.columns else []
        if len(hands)>=2:
            with viz_card("SPRAY POR MANO","Dónde caen los batazos por mano","Spray chart contra cada mano del pitcher."):
                cols_h=st.columns(len(hands))
                for col_h,hand in zip(cols_h,sorted(hands)):
                    with col_h:
                        sub_h=bdf[bdf["PitcherThrows"]==hand]
                        png_h=render_spray_png(spray_points(sub_h),hitting_summary(sub_h,lmeta),
                                               f"{selected} vs {hand}",color_by="ev")
                        if png_h: st.image(png_h,use_container_width=True)
                        else: st.info("Sin datos de spray.")
    with tab3:
        result_df=build_play_result_table(bdf)
        with viz_card("RESULTADOS DE JUGADA","Distribución de resultados","Conteo y % de PAs por resultado."):
            if result_df.empty: st.info("PlayResult column not found.")
            else:
                st.dataframe(result_df,use_container_width=True,hide_index=True)
                csv_dl(result_df,f"{selected}_results.csv")
    with tab4:
        with viz_card("SPRAY CHART","Dónde caen los batazos","Campo top-down; toggle Pro/Interactivo y color por EV o resultado."):
            cv1,cv2=st.columns(2)
            with cv1: sv=st.radio("Vista",["🖼️ Pro","🔍 Interactivo"],key="hit_spray_view",horizontal=True)
            with cv2: sc=st.radio("Color",["Exit Velocity","Resultado"],key="hit_spray_color",horizontal=True)
            cb="ev" if sc=="Exit Velocity" else "result"
            pts=spray_points(bdf)
            if sv=="🖼️ Pro":
                png=render_spray_png(pts,summ,selected,color_by=cb)
                if png: st.image(png,use_container_width=True)
                else: st.info("Sin datos de spray (Distance/Bearing).")
            else:
                st.plotly_chart(vhit.spray_interactive(pts,selected,color_by=cb),use_container_width=True)
        with viz_card("DAMAGE ZONE","Dónde le pegan más duro","EV por ubicación del pitcheo en la zona."):
            st.plotly_chart(vhit.damage_zone(bdf,selected),use_container_width=True)
    with tab5:
        cl2,cr2=st.columns(2)
        with cl2:
            with viz_card("EXIT VELOCITY","Distribución de EV","Histograma de Exit Velocity; línea de Hard Hit (95)."):
                st.plotly_chart(vhit.ev_distribution(bdf,selected),use_container_width=True)
        with cr2:
            with viz_card("LAUNCH ANGLE","Distribución de LA","Histograma de Launch Angle; sweet-spot 8–32°."):
                st.plotly_chart(vhit.la_distribution(bdf,selected),use_container_width=True)
        with viz_card("HIT QUALITY MAP","Exit Velocity × Launch Angle","Cada batazo por EV y LA, con la zona barrel."):
            st.plotly_chart(vhit.ev_la_scatter(bdf,selected),use_container_width=True)
    with tab6:
        st.info("Stadium analysis coming soon.")
```

Nota: `monthly_df`, `split_df`, `result_df` siguen definidos dentro de los tabs (los usa el PDF export más abajo, que no cambia). No tocar métricas de cabecera, plate discipline, percentiles ni export.

- [ ] **Step 2: Verificar sintaxis + import + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('syntax ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: syntax ok, import ok, 70 passed.

- [ ] **Step 3: Commit**

```bash
git add trackman_app.py
git commit -m "feat: envolver gráficos/tablas de Hitting en tarjetas viz_card"
```

---

### Task 3: Verificación visual (Playwright) + changelog + merge

- [ ] **Step 1: Levantar el app con un CSV sintético y capturar el modo Hitting**

Crear un CSV de bateo en una carpeta temporal, arrancar Streamlit headless, y con Playwright:
seleccionar fuente "🏆 Carpeta local", escribir la ruta, elegir modo "🏏 Hitting", ir al tab Spray y
capturar. Script de referencia (ajustar selectores/timeouts en ejecución):

```python
import subprocess, time, tempfile, os, numpy as np, pandas as pd
from playwright.sync_api import sync_playwright
d = tempfile.mkdtemp(); sub = os.path.join(d, "torneo"); os.makedirs(sub)
np.random.seed(3); n=120
pd.DataFrame({
  "Batter":"B. Perez","Pitcher":"X","TaggedPitchType":np.random.choice(["Fastball","Slider"],n),
  "PitchCall":np.random.choice(["InPlay","StrikeCalled","StrikeSwinging","BallCalled","FoulBall"],n,p=[.4,.15,.12,.23,.10]),
  "PlayResult":np.random.choice(["1B","2B","HR","Out","K","BB","Undefined"],n,p=[.12,.05,.05,.4,.13,.08,.17]),
  "ExitSpeed":np.clip(np.random.normal(90,12,n),55,115),"Angle":np.clip(np.random.normal(14,18,n),-30,70),
  "Distance":np.clip(np.random.normal(220,110,n),40,430),"Bearing":np.random.uniform(-42,42,n),
  "PlateLocSide":np.random.randn(n)*0.6,"PlateLocHeight":2.5+np.random.randn(n)*0.6,
  "PitcherThrows":np.random.choice(["R","L"],n),"Date":pd.to_datetime(np.random.choice(pd.date_range("2026-05-01","2026-07-01"),n)),
}).to_csv(os.path.join(sub,"data.csv"),index=False)
p = subprocess.Popen([".venv/bin/streamlit","run","trackman_app.py","--server.headless","true","--server.port","8555"])
time.sleep(9)
SC="/private/tmp/claude-501/-Users-joseramirez/07df3a36-c748-4f6e-8aa0-4731db9dfab5/scratchpad/refs"
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width":1500,"height":2200})
        pg.goto("http://localhost:8555", wait_until="networkidle", timeout=60000)
        pg.get_by_text("🏆 Carpeta local", exact=False).click(); pg.wait_for_timeout(1500)
        pg.get_by_placeholder("/Users").fill(d); pg.keyboard.press("Enter"); pg.wait_for_timeout(4000)
        pg.get_by_text("🏏 Hitting", exact=False).click(); pg.wait_for_timeout(4000)
        pg.get_by_text("🗺️ Spray", exact=False).click(); pg.wait_for_timeout(3000)
        pg.screenshot(path=f"{SC}/_hit_app.png", full_page=True); b.close()
finally:
    p.terminate()
```
Ver `_hit_app.png` y comparar con el preview.

- [ ] **Step 2: Iterar** el CSS/espaciado en `trackman_app.py` si hace falta; re-capturar; sign-off del founder.
- [ ] **Step 3: Changelog** v4.13 en `README.md` (Hitting con tarjetas + tema claro fijado).
- [ ] **Step 4: Merge a `main`** (push → PR → merge → borrar rama → sync → tests).

---

## Self-Review

**1. Spec coverage:** tema fijado (Task 1 Step 1), viz_card+CSS (Task 1), envolver todo Hitting (Task 2), verificación Playwright + changelog + merge (Task 3). ✓
**2. Placeholder scan:** el script Playwright dice "ajustar selectores/timeouts en ejecución" — inevitable en automatización de UI; el script es completo y funcional como punto de partida. El resto tiene código completo.
**3. Type consistency:** `viz_card(eyebrow, title, desc="")` definido en Task 1 y usado con esa firma en Task 2. ✓

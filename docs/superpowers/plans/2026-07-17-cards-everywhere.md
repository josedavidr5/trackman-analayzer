# Tarjetas en Pitching/League/Top Plays — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development o superpowers:executing-plans. Steps con checkbox (`- [ ]`). La Task 3 (captura Playwright) requiere ver imágenes — trabajo de controller.

**Goal:** Dejar Pitching, League y Top Plays con la misma presentación de tarjetas que Hitting (`viz_card`).

**Architecture:** Reusar el helper `viz_card` (ya existe) para envolver cada gráfico/tabla, reemplazando los encabezados `<div class="sh">`. Sin lógica nueva.

**Tech Stack:** Streamlit, `viz_card` (`st.container(border=True)` + CSS), Playwright para verificación.

## Global Constraints

- Solo **presentación** de Pitching/League/Top Plays. No tocar analítica, gráficos, hero, sidebar, tema, Hitting ni 3D.
- `trackman_app.py` usa **CRLF**.
- `with viz_card(...)` NO crea scope: variables asignadas dentro (p.ej. `summary_df`, `disc_df`) siguen accesibles para el PDF.
- Verificación: `import trackman_app` OK + captura Playwright + suite existente verde (70).

---

### Task 1: Tarjetas en `render_pitching`

**Files:** Modify `trackman_app.py` (tabs de `render_pitching`, actual :1347-1389)

- [ ] **Step 1: Reemplazar el contenido de los tabs** por la versión con tarjetas:

```python
    with tab1:
        with viz_card("ARSENAL — STUFF", "Arsenal del pitcher", "Movimiento por tipo (hover: velo/spin/whiff/CSW) + tabla con CSW%."):
            st.checkbox("Mostrar pitcheos individuales", value=True, key="arsenal_show_ind")
            st.plotly_chart(fig_mov, use_container_width=True)
            summary_df = arsenal_stuff(pf)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            csv_dl(summary_df, f"{selected}_arsenal.csv")
        with viz_card("DISCIPLINA", "Zona, swing y contacto", "Zone%, Swing%, Contact%, Chase%, Whiff% por tipo."):
            disc_df = compute_pitch_discipline(pf)
            if disc_df.empty:
                st.info("PitchCall column required.")
            else:
                st.dataframe(disc_df, use_container_width=True, hide_index=True)
                csv_dl(disc_df, f"{selected}_discipline.csv")
    with tab2:
        with viz_card("UBICACIÓN", "Dónde ubica sus pitcheos", "Ubicaciones y densidad (hot zone) sobre la zona de strike."):
            cl, cr = st.columns(2)
            with cl: st.plotly_chart(fig_loc, use_container_width=True)
            with cr: st.plotly_chart(fig_kde, use_container_width=True)
        with viz_card("POR TIPO DE PITCHEO", "Ubicación por tipo", "Un panel de ubicación por cada tipo de pitcheo."):
            st.plotly_chart(vpitch.location_by_pitch(pf, selected), use_container_width=True)
    with tab3:
        with viz_card("TENDENCIA DE VELOCIDAD", "Velo en el tiempo", "Exit velocity por fecha, por tipo de pitcheo."):
            st.plotly_chart(fig_vel, use_container_width=True)
        with viz_card("USO POR CONTEO", "Qué lanza en cada conteo", "Heatmap de uso % por tipo de pitcheo y conteo (bolas-strikes)."):
            st.plotly_chart(vpitch.usage_heatmap(build_usage_by_count(pf), selected), use_container_width=True)
    with tab4:
        with viz_card("WHIFF% / CSW% POR ZONA", "Dónde consigue sus misses", "Grid por zona; selector de tipo de pitcheo y toggle Whiff/CSW."):
            ptypes = ["Todos"] + sorted(pf["TaggedPitchType"].dropna().unique().tolist())
            cq1, cq2 = st.columns([2, 3])
            with cq1:
                sel_pt = st.selectbox("Tipo de pitcheo", ptypes, key="whiffcsw_ptype")
            with cq2:
                sel_metric = st.radio("Métrica", ["Whiff %", "CSW %"], key="whiffcsw_metric", horizontal=True)
            sub = pf if sel_pt == "Todos" else pf[pf["TaggedPitchType"] == sel_pt]
            grid = whiff_csw_zone_grid(sub)
            metric = "whiff" if sel_metric == "Whiff %" else "csw"
            st.plotly_chart(vpitch.zone_rate_heatmap(grid, metric, f"{selected} · {sel_pt}"), use_container_width=True)
            st.caption(f"{grid['total_pitches']} pitcheos con ubicación · "
                       "celdas con muestra baja (Whiff <4 swings / CSW <5 pitcheos) en gris con solo el conteo.")
    with tab5:
        st.info("Stadium analysis coming soon.")
```

- [ ] **Step 2: Verificar sintaxis + import + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: ok, import ok, 70 passed.

- [ ] **Step 3: Commit**

```bash
git add trackman_app.py
git commit -m "feat: tarjetas viz_card en render_pitching"
```

---

### Task 2: Tarjetas en `render_league` y `render_top_plays`

**Files:** Modify `trackman_app.py`

- [ ] **Step 1: `render_league` — envolver las 2 tablas** (actual :1538-1553):

```python
    with tab_l1:
        c1,c2=st.columns(2)
        with c1:
            with viz_card("PROMEDIOS DE LIGA — PITCHING", "Arsenal de la liga", "Velo, spin y movimiento promedio por tipo de pitcheo."):
                lp=build_league_pitching_avg(df)
                if lp.empty: st.info("Insufficient data.")
                else:
                    st.dataframe(lp,use_container_width=True,hide_index=True)
                    csv_dl(lp,"league_pitching.csv")
        with c2:
            with viz_card("PROMEDIOS DE LIGA — HITTING", "Bateo de la liga", "EV, LA, HH%, Barrel%, K/BB y wOBA promedio."):
                lh=build_league_hitting_avg(df,lmeta)
                if lh.empty: st.info("Insufficient data.")
                else:
                    st.dataframe(lh,use_container_width=True,hide_index=True)
                    csv_dl(lh,"league_hitting.csv")
```

- [ ] **Step 2: `render_top_plays` — leaderboard en tarjeta** (actual :1143-1146):

Reemplazar:
```python
    st.markdown(f'<div class="sh">{meta["title"]}{" · "+area_label if area_label else ""} · {dr}</div>',
                unsafe_allow_html=True)
    st.dataframe(lb,use_container_width=True)
    csv_dl(lb,"top_plays.csv")
```
por:
```python
    with viz_card("LEADERBOARD", f'{meta["title"]}{" · "+area_label if area_label else ""}', dr):
        st.dataframe(lb,use_container_width=True)
        csv_dl(lb,"top_plays.csv")
```

- [ ] **Step 3: `render_top_plays` — tarjeta para redes en `viz_card`** (actual :1171-1183):

Reemplazar:
```python
    st.markdown('<div class="sh">📱 Tarjeta para redes sociales</div>',unsafe_allow_html=True)
    card_sub=dr+(f" · {area_label}" if area_label else "")
    fig_card=make_social_card(lb,meta,card_sub,tournament)
    cl,cr=st.columns([2,1])
    with cl: st.pyplot(fig_card,use_container_width=True)
    with cr:
        st.caption("Imagen 1080×1080 lista para Instagram / X / Facebook.")
        buf=io.BytesIO()
        fig_card.savefig(buf,format="png",dpi=100,facecolor=fig_card.get_facecolor())
        buf.seek(0)
        st.download_button("⬇️ Descargar PNG",buf.read(),
                           f"top_plays_{meta['value_col'].lower()}.png","image/png")
    plt.close(fig_card)
```
por:
```python
    with viz_card("TARJETA PARA REDES", "Contenido listo para compartir", "Imagen 1080×1080 para Instagram / X / Facebook."):
        card_sub=dr+(f" · {area_label}" if area_label else "")
        fig_card=make_social_card(lb,meta,card_sub,tournament)
        cl,cr=st.columns([2,1])
        with cl: st.pyplot(fig_card,use_container_width=True)
        with cr:
            buf=io.BytesIO()
            fig_card.savefig(buf,format="png",dpi=100,facecolor=fig_card.get_facecolor())
            buf.seek(0)
            st.download_button("⬇️ Descargar PNG",buf.read(),
                               f"top_plays_{meta['value_col'].lower()}.png","image/png")
        plt.close(fig_card)
```
(La sección "por región" con el `st.expander` se mantiene tal cual — ya es un contenedor colapsable.)

- [ ] **Step 4: Verificar sintaxis + import + suite**

Run: `cd /Users/joseramirez/trackman-analayzer && .venv/bin/python -c "import ast; ast.parse(open('trackman_app.py').read()); print('ok')" && .venv/bin/python -c "import trackman_app; print('import ok')" && .venv/bin/python -m pytest core/tests/ viz/tests/ trajectory/tests/ -q`
Expected: ok, import ok, 70 passed.

- [ ] **Step 5: Commit**

```bash
git add trackman_app.py
git commit -m "feat: tarjetas viz_card en render_league y render_top_plays"
```

---

### Task 3: Verificación visual (Playwright) + changelog + merge

- [ ] **Step 1: Capturar Pitching + League** con el script de iter 5 (adaptar los clicks de modo/tab a Pitching y League) y verlos; comparar con Hitting (tarjetas consistentes).
- [ ] **Step 2: Iterar** espaciado/títulos si hace falta.
- [ ] **Step 3: Changelog** v4.14 en `README.md` (tarjetas en Pitching/League/Top Plays; app consistente).
- [ ] **Step 4: Merge a `main`** (push → PR → merge → borrar rama → sync → tests).

---

## Self-Review

**1. Spec coverage:** Pitching cards (Task 1), League cards (Task 2 Step 1), Top Plays leaderboard + social (Task 2 Steps 2-3), verificación/changelog/merge (Task 3). ✓
**2. Placeholder scan:** El script Playwright de Task 3 Step 1 dice "adaptar los clicks" — se reusa `capture_hitting.py` de iter 5 cambiando el modo/tab; inevitable en automatización de UI. Resto con código completo.
**3. Type consistency:** `viz_card(eyebrow, title, desc="")` usado con esa firma en todos lados; `summary_df`/`disc_df` siguen en scope tras el `with` (no crea scope). ✓

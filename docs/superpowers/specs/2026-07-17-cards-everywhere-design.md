# Iteración 6 — Consistencia de tarjetas (Pitching + League + Top Plays)

**Fecha:** 2026-07-17
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Presentación de los modos **⚾ Pitching**, **📊 League** y **🔥 Top Plays** en `trackman_app.py`.

## Contexto

En la iter 5 se llevó **Hitting** al look de tarjetas (`viz_card`: etiqueta + título + descripción,
en `st.container(border=True)`). Pitching, League y Top Plays siguen con gráficos/tablas "pelados"
(`st.markdown('<div class="sh">…')` + `st.plotly_chart`/`st.dataframe` directos), por lo que el
modo estrella (Pitching) se ve **inferior** a Hitting. El founder pidió dejar **todo el app
consistente**. Es un cambio de **presentación solamente** (reusa `viz_card`, ya existente). El tema
claro ya quedó fijado en la iter 5.

## Diseño

Envolver cada gráfico/tabla de los 3 modos en `viz_card(eyebrow, title, desc)`, reemplazando los
encabezados `<div class="sh">…</div>` por la cabecera de la tarjeta.

### ⚾ Pitching (`render_pitching`)
| Tab | Tarjetas |
|-----|----------|
| 📋 Summary | "ARSENAL — STUFF" (checkbox + bubble de movimiento + tabla `arsenal_stuff`) · "DISCIPLINA" (tabla) |
| 📍 Location | "UBICACIÓN" (scatter + hot zone, 2 columnas) · "POR TIPO DE PITCHEO" (`location_by_pitch`) |
| 📊 Trends | "TENDENCIA DE VELOCIDAD" (`velo_trend`) · "USO POR CONTEO" (`usage_heatmap`) |
| 🎯 Whiff/CSW | "WHIFF% / CSW% POR ZONA" (selector de tipo + toggle métrica + heatmap + caption) |
| 🏟️ Stadium | sin cambios ("coming soon") |

Importante: `summary_df` y `disc_df` se calculan dentro de la tarjeta de Summary y siguen usándose
en el botón de PDF (fuera de las tarjetas); el `with viz_card(...)` no crea scope nuevo, así que
las variables permanecen accesibles. No cambian las métricas de cabecera, percentiles ni export.

### 📊 League (`render_league`)
- Tab **League Averages**: "PROMEDIOS DE LIGA — PITCHING" (tabla `build_league_pitching_avg`) y
  "— HITTING" (tabla `build_league_hitting_avg`), en 2 columnas.
- Tab Stadium: sin cambios.

### 🔥 Top Plays (`render_top_plays`)
- "LEADERBOARD" — la tabla principal del ranking (`st.dataframe(lb)`).
- "POR REGIÓN" — las tablas + tarjetas PNG por región (cuando aplica).
- "TARJETA PARA REDES" — el preview de `make_social_card` + botón de descarga.
- El editor de regiones y el parser de preguntas (inputs) se mantienen tal cual arriba; solo los
  bloques de resultados van en tarjetas.

## Verificación

Como es presentación, la verificación es visual y real (Playwright, ya montado en iter 5):
1. Levantar el app con un CSV sintético (modo "🏆 Carpeta local").
2. **Capturar Pitching** (tabs Summary/Location) y **League** con Playwright y verlos.
3. Confirmar que las tarjetas se ven consistentes con Hitting; iterar espaciado si hace falta.
4. Sign-off del founder.

## Testing
- Sin lógica nueva; se mantiene la suite existente verde (70 tests).
- Verificación: `import trackman_app` OK + captura Playwright.

## No-goals (YAGNI)
- Sin cambiar analítica, gráficos, spray render ni el parser de Top Plays.
- Sin tocar el hero, el sidebar ni el tema (ya fijado en iter 5).
- Sin cambiar Hitting (ya tiene tarjetas) ni el modo 3D.

## Criterios de aceptación
- [ ] Pitching: todos los gráficos/tablas de los tabs Summary/Location/Trends/Whiff-CSW en `viz_card`.
- [ ] League: las 2 tablas de promedios en `viz_card`.
- [ ] Top Plays: leaderboard, por-región y tarjeta-para-redes en `viz_card`.
- [ ] Captura Playwright de Pitching + League comparada con Hitting; sign-off del founder.
- [ ] Suite verde; `import trackman_app` OK; sin regresión.

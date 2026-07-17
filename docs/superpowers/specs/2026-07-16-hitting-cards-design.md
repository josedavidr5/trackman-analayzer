# Iteración 5 — Presentación de Hitting (tarjetas) + tema fijado

**Fecha:** 2026-07-16
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Presentación del modo **🏏 Hitting** en `trackman_app.py` + configuración de tema.

## Contexto

Tras la iter 4, el founder vio el **preview** (artefacto con tarjetas: etiqueta + título +
descripción + gráfico en contenedor limpio) y le gustó, pero al ver el **app en producción** no le
gustó. Su instrucción: *"vamos otra vez a trabajar hitting y que se vea todo así"*, eligiendo
explícitamente **"solo las tarjetas/presentación"** — es decir, **mantener el tema claro del app**
(Savant) y envolver los gráficos en tarjetas bien presentadas como el preview.

### Diagnóstico (por qué producción se ve mal)
El app **no tiene `.streamlit/config.toml`** → Streamlit sigue el **tema del sistema operativo** del
visitante. El CSS del app está diseñado para **claro** (fondos blancos, badges `#fafafa`, azul
`#1f77b4`) y las figuras Plotly tienen **fondo blanco fijo** (`viz/theme.py`: `paper_bgcolor="#ffffff"`).
Si el visitante está en **modo oscuro**, Streamlit pinta la app oscura y el CSS/gráficos claros
quedan descuadrados. Fijar el tema elimina esa variable.

## Diseño

### 1. Fijar el tema a claro
Crear `.streamlit/config.toml`:
```toml
[theme]
base = "light"
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#fafafa"
textColor = "#333333"
```
Garantiza que producción (local y Streamlit Cloud) se vea como el diseño, sin depender del SO del
visitante. Es coherente con el look Savant claro que el founder quiere conservar.

### 2. Helper de tarjeta (`viz_card`)
En `trackman_app.py`, junto a los demás helpers de UI:
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
Usa `st.container(border=True)` (nativo en Streamlit 1.59.2 — verificado) para el borde/redondeo, y
CSS propio para la tipografía de la cabecera.

### 3. CSS nuevo (añadir al bloque `<style>` existente)
```css
.viz-eyebrow{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.62rem;
  letter-spacing:.18em;text-transform:uppercase;color:#1f77b4;font-weight:700;margin-bottom:2px}
.viz-title{font-size:1.05rem;font-weight:800;letter-spacing:-.01em;line-height:1.2;
  margin-bottom:3px;color:#222}
.viz-desc{font-size:.82rem;color:#5b6b78;line-height:1.45;margin-bottom:8px}
```
Reusa la paleta existente del app (azul `#1f77b4`, texto `#333`), sin introducir un sistema nuevo.

### 4. Aplicar a todo el modo Hitting (`render_hitting`)
Cada gráfico y cada tabla va dentro de una `viz_card` con etiqueta / título / descripción:

| Tab | Tarjetas |
|-----|----------|
| 📅 Monthly | "PROGRESIÓN MENSUAL" (tabla) · "ROLLING EV" (gráfico) |
| 🔄 Splits | "SPLITS vs RHP/LHP" (tabla) · "SPRAY POR MANO" (una tarjeta por mano) |
| 📋 Results | "RESULTADOS DE JUGADA" (tabla) |
| 🗺️ Spray | "SPRAY CHART" (toggles + Pro/Interactivo) · "DAMAGE ZONE" (gráfico) |
| 📊 Distributions | "EXIT VELOCITY" · "LAUNCH ANGLE" · "HIT QUALITY MAP (EV × LA)" |

Los toggles del spray (Pro/Interactivo, EV/Resultado) van **dentro** de su tarjeta, arriba del gráfico.
El resto de la página (hero, métricas, plate discipline, percentiles, export) **no cambia**.

## Verificación

Como es un cambio de presentación, la verificación es visual y **real** (no teórica):
1. Levantar el app con Streamlit y un CSV sintético de bateo (modo "🏆 Carpeta local" apuntando a una
   carpeta temporal con el CSV).
2. **Capturar el modo Hitting con Playwright** (ya instalado: chromium) y ver la captura.
3. Comparar contra el preview (tarjetas: etiqueta + título + descripción + gráfico en contenedor).
4. Iterar el CSS/espaciado si hace falta; sign-off del founder.

## Testing
- No hay lógica nueva que testear (es presentación). Se mantiene la suite existente verde (70 tests).
- Verificación: `import trackman_app` OK + captura Playwright del modo Hitting.

## No-goals (YAGNI)
- No tocar Pitching / League / Top Plays / Trayectorias 3D (solo Hitting).
- Sin dark mode (el founder eligió conservar el tema claro).
- Sin cambiar analítica, gráficos ni el spray render.
- Sin rediseñar el hero/sidebar.

## Criterios de aceptación
- [ ] `.streamlit/config.toml` fija el tema claro (producción ya no depende del SO).
- [ ] `viz_card` + CSS (`.viz-eyebrow`, `.viz-title`, `.viz-desc`) en el app.
- [ ] Todos los gráficos y tablas de Hitting envueltos en tarjetas con etiqueta/título/descripción.
- [ ] Captura Playwright del modo Hitting comparada con el preview; sign-off del founder.
- [ ] Suite verde; sin regresión en otros modos.

# Iteración 7 — Stats esperados + Run Value (capa evaluativa)

**Fecha:** 2026-07-22
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Alcance:** Nueva capa analítica `core/expected.py` + wiring en Hitting, Pitching y League de `trackman_app.py`.

## Contexto

Hoy el app es una colección de **dashboards descriptivos**: Pitching, Hitting, League y Top Plays
muestran *qué pasó* (EV, velo, spin, resultados). Lo que falta para ser un verdadero **sistema de
análisis** es la capa **evaluativa**: medir *qué tan bueno fue* el contacto/pitcheo más allá del
resultado en el marcador, quitando la suerte y la defensa de la ecuación. Esta iteración agrega
**expected stats** (xwOBA/xBA/xSLG) y **run value** — la moneda real del béisbol (carreras).

## Objetivos — qué responde

- **xwOBA / xBA / xSLG** por batazo y por PA: "¿qué tan bueno fue el contacto, más allá de si cayó de hit?"
- **Expected vs actual** por jugador: quién sobre/sub-rinde (indicador de suerte/regresión).
- **Run value**: traducir todo a carreras — qué bateador/pitcher/pitcheo suma o resta vs el promedio.

## Diseño

### Modelo de resultado esperado (híbrido MLB + tus datos)

Una superficie **EV × ángulo → vector de probabilidad** sobre `{out, 1B, 2B, 3B, HR}`.

**(a) Base MLB calibrada — paramétrica.** `base_outcome_probs(ev, la) -> np.ndarray[5]`. Un modelo
paramétrico e interpretable (no una tabla a mano) que reproduce la forma conocida de la superficie de
Statcast:
- **HR**: producto de una logística en EV (centro ≈ 100 mph) por una campana gaussiana en LA
  (centro ≈ 28°, ancho ≈ 8°) — el "barrel window".
- **Extra-base en aire** (2B/3B): línea/fly duros fuera del window de HR.
- **1B**: rasos duros (grounders con EV alto) y líneas suaves.
- **out** = `1 − (P1B+P2B+P3B+PHR)`, garantizando vector válido (clip a [0,1], renormaliza).

La calibración se fija con **anclas verificables** (son los tests; los coeficientes se ajustan por TDD
hasta pasarlas). xwOBA-on-contact esperado en cada ancla (con tolerancia ±0.08 salvo nota):
| Escenario | EV | LA | xwOBA objetivo |
|-----------|----|----|----------------|
| Barrel | 100 | 28 | ≈ 0.95 (≥ 0.85) |
| Línea dura | 95 | 15 | ≈ 0.65 |
| Contacto promedio | 89 | 12 | ≈ 0.37 |
| Roletazo débil | 70 | -5 | ≈ 0.12 (≤ 0.20) |
| Popup | 80 | 50 | ≈ 0.04 (≤ 0.10) |

Propiedades (también tests): monotonía — subir EV en la zona de línea (LA 10–25°) nunca baja xwOBA;
un popup (LA>45) siempre da xwOBA menor que una línea a la misma EV; probabilidades válidas (suman 1,
todas ≥0) en todo el rango EV∈[40,120], LA∈[-40,60].

**(b) Recalibración empírica (lo híbrido).** `empirical_grid(df) -> dict[(ev_bin,la_bin) -> (counts5, n)]`
cuenta resultados reales por celda EV×LA (bins de 5 mph × 5°) desde los batazos del dataset
(`batted_ball_mask`; mapeo de PlayResult BIP → 5 clases: `1B/2B/3B/HR` directos, y `Out/FC/Error/SacFly`
→ `out`). Luego `hybrid_outcome_probs(ev, la, grid, k=50)` mezcla por **shrinkage bayesiano**:
`p = (n·p_emp + k·p_base) / (n + k)`, donde `p_base` es la base MLB y `p_emp` las tasas empíricas de la
celda. Con `n→0` tiende a MLB; con `n→∞` tiende a tu liga. **Flag de recalibración activa** cuando el
total de batazos válidos ≥ **500** (la UI muestra "recalibrado con tu liga · N batazos"; por debajo,
"modelo base MLB").

### x-stats (reusa las constantes existentes de `core/metrics.py`)

- `xwoba_contact(ev, la, grid=None)` = `Σ p[outcome]·WOBA_W[outcome]` (out→0), usando el modelo híbrido
  si se pasa `grid`, si no la base. Reusa `WOBA_W` de `core.metrics`.
- `expected_batted_balls(df, grid=None) -> DataFrame` con columnas `xwoba, xba, xslg` por batazo
  (`xba` = P(hit)=P1B+P2B+P3B+PHR; `xslg` = 1·P1B+2·P2B+3·P3B+4·PHR).
- `xwoba_pa(df, grid=None) -> float`: espeja `compute_woba` — numerador = `Σ_bip xwoba_contact` +
  `Σ_nonbip WOBA_W[res]` (K→0, BB, HBP reales), denominador = `count_pa(df) − #SacBunt`. Devuelve `np.nan`
  sin datos de PA.
- `expected_summary(df, grid=None) -> dict`: `{xwoba, xba, xslg, woba, woba_minus_xwoba, n_bip}` para
  tarjetas (woba actual vía `compute_woba`; `woba_minus_xwoba` = over/under-performance).

### Run value (Fase B)

- Constantes documentadas MLB (configurables, marcadas como tales): `LG_WOBA = 0.320`,
  `WOBA_SCALE = 1.25`.
- `run_value_woba(woba, pa)` = `((woba − LG_WOBA)/WOBA_SCALE)·pa` (carreras vs promedio). Se aplica a
  wOBA actual y a xwOBA (run value esperado).
- **Run value por pitcheo** (pieza fuerte de la Fase B): tabla de run-expectancy por conteo
  (`RE_BY_COUNT`, 12 estados bolas-strikes, valores lineales documentados) + valor de eventos terminales;
  `pitch_run_values(df)` = Δ run-expectancy entre el conteo previo y el siguiente/terminal por pitcheo.
  Agregado `RV/100` por tipo de pitcheo → base de un futuro "Stuff+".

### Wiring por vista (`trackman_app.py`)

- **Hitting** (`render_hitting`): tarjeta nueva "VALOR ESPERADO" con xwOBA/xBA/xSLG y **actual vs expected**
  (wOBA vs xwOBA; barra o métrica de sobre/sub-rendimiento). Usa `viz_card` (consistencia iter 6).
- **Pitching** (`render_pitching`): **xwOBA-contra** por pitcher (tarjeta) y por tipo de pitcheo (columna
  nueva en `arsenal_stuff`, o tabla contigua) — "qué pitcheo suprime más valor".
- **League** (`render_league`): benchmark de liga en xwOBA (agrega a la tabla de hitting de liga).
- El `grid` empírico se calcula una vez sobre el dataset completo cargado (cacheado) y se pasa a las vistas.

## Fases (cada una mergea a `main`)

- **Fase A — Expected stats (PR #7):** `core/expected.py` con el modelo híbrido + x-stats + tests de
  anclas/monotonía/PA; wiring en Hitting (tarjeta VALOR ESPERADO) y Pitching (xwOBA-contra) y League.
  Deliverable completo y shippable.
- **Fase B — Run value (PR #8):** run value por PA (wOBA scaling) + run value por pitcheo (RE por conteo)
  → RV/100 por tipo de pitcheo en el arsenal y leaderboard de valor.

## Testing

- `core/tests/test_expected.py` (pytest, pura):
  - **Anclas**: cada escenario de la tabla cae en su rango de xwOBA.
  - **Monotonía**: xwOBA sube con EV en la banda de línea; popup < línea a igual EV.
  - **Validez**: `base_outcome_probs` suma 1 y ≥0 en una malla EV×LA.
  - **Shrinkage**: `hybrid` con `n=0` ≈ base; con celda empírica dominante y `n` grande ≈ empírico.
  - **xwoba_pa**: dataset con K/BB reales + batazos → numerador y denominador correctos; `np.nan` sin PA.
- Verificación visual Playwright del wiring (Hitting/Pitching) — tarjetas se ven bien y consistentes.
- La suite existente (70) se mantiene verde; `import trackman_app` OK.

## No-goals (YAGNI)

- Sin modelo ML entrenado ni dependencias nuevas — el modelo base es paramétrico, en numpy.
- Sin sprint speed / posición de fildeo (no está en los datos) — xwOBA solo por EV+ángulo (xwOBACON).
- Sin vista nueva dedicada: el "expected" vive al lado del "actual" en las vistas existentes.
- Sin tocar Top Plays / 3D / tema / hero en esta iteración (Top Plays queda para después).
- Run value por pitcheo completo se limita a Fase B; la Fase A no lo incluye.

## Criterios de aceptación

- [ ] `core/expected.py` con modelo híbrido, x-stats por batazo y por PA; tests de anclas/monotonía/PA verdes.
- [ ] Hitting muestra tarjeta VALOR ESPERADO (xwOBA/xBA/xSLG + actual vs expected).
- [ ] Pitching muestra xwOBA-contra (por pitcher y por tipo de pitcheo).
- [ ] League incluye xwOBA en el benchmark de hitting.
- [ ] UI indica si el modelo está recalibrado con la liga (≥500 batazos) o es base MLB.
- [ ] Suite verde; `import trackman_app` OK; verificación visual con sign-off del founder.
- [ ] (Fase B) run value por PA y por pitcheo (RV/100 por tipo) — en su propio PR.

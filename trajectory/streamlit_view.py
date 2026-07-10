"""
trajectory.streamlit_view — frontend del módulo de trayectorias.
Vista 3D "detrás del catcher" con animación (Plotly), heatmaps por conteo,
break chart, release consistency, tendencias, comparación de pitchers y export.

Importado por trackman_app.py:  from trajectory.streamlit_view import render_trajectory_mode
"""
from __future__ import annotations
import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from .engine import compute_pitch_path, pitch_metrics, PLATE_Y
from .validation import validate_schema, validate_physical
from .analytics import (ensure_pitch_ids, movement_profile,
                        release_consistency, velocity_spin_trends)

PALETTE = ["#1f77b4","#d62728","#2ca02c","#ff7f0e","#9467bd",
           "#8c564b","#e377c2","#7f7f7f","#17becf","#bcbd22"]
# Colores oficiales Statcast/Savant por tipo de pitcheo (v4.5)
STATCAST_COLORS={
    "4-Seam":"#D22D49","Fastball":"#D22D49","Four-Seam Fastball":"#D22D49",
    "2-Seam":"#DE6A04","Sinker":"#FE9D00","Cutter":"#933F2C","Slider":"#C3BD0E",
    "Sweeper":"#DDB33A","Curve":"#00D1ED","Curveball":"#00D1ED",
    "Change":"#1DBE3A","Changeup":"#1DBE3A","Split":"#3BACAC",
    "Knuckleball":"#3C44CD","Screwball":"#60DB33",
}
def _pt_color(pt, idx=0):
    return STATCAST_COLORS.get(str(pt), PALETTE[idx % len(PALETTE)])
ZONE_X, ZONE_LO, ZONE_HI = 0.83, 1.5, 3.5


def _zone_traces():
    """Zona de strike (grid 3×3) + plato en 3D, en y = frente del plato."""
    traces = []
    y = PLATE_Y
    # marco
    traces.append(go.Scatter3d(
        x=[-ZONE_X,ZONE_X,ZONE_X,-ZONE_X,-ZONE_X], y=[y]*5,
        z=[ZONE_LO,ZONE_LO,ZONE_HI,ZONE_HI,ZONE_LO],
        mode="lines", line=dict(color="#555", width=5),
        name="Zona de strike", showlegend=False, hoverinfo="skip"))
    # grid interno
    for f in (1/3, 2/3):
        gx = -ZONE_X + 2*ZONE_X*f
        gz = ZONE_LO + (ZONE_HI-ZONE_LO)*f
        traces.append(go.Scatter3d(x=[gx,gx], y=[y,y], z=[ZONE_LO,ZONE_HI],
            mode="lines", line=dict(color="#999", width=2), showlegend=False, hoverinfo="skip"))
        traces.append(go.Scatter3d(x=[-ZONE_X,ZONE_X], y=[y,y], z=[gz,gz],
            mode="lines", line=dict(color="#999", width=2), showlegend=False, hoverinfo="skip"))
    # plato
    traces.append(go.Scatter3d(
        x=[-0.71,0.71,0.71,0,-0.71,-0.71], y=[y,y,0.2,0,0.2,y], z=[0.02]*6,
        mode="lines", line=dict(color="#888", width=4), showlegend=False, hoverinfo="skip"))
    return traces


def _pitch_label(row):
    v = row.get("RelSpeed"); s = row.get("SpinRate")
    bits = [str(row.get("TaggedPitchType","?"))]
    if pd.notna(v): bits.append(f"{float(v):.1f} mph")
    if pd.notna(s): bits.append(f"{float(s):.0f} rpm")
    return " · ".join(bits)


def build_3d_figure(rows, n_points=50, title=""):
    """
    Figura 3D animada con múltiples pitches superpuestos.
    Play/pause + slider de frames para scrubbing manual.
    """
    paths, labels, colors, metas = [], [], [], []
    for i, (_, r) in enumerate(rows.iterrows()):
        try:
            paths.append(compute_pitch_path(r, n_points=n_points))
        except ValueError:
            continue
        labels.append(_pitch_label(r))
        colors.append(_pt_color(r.get("TaggedPitchType"), i))
        metas.append(pitch_metrics(r))
    if not paths:
        return None, []
    base = list(_zone_traces())
    for path, lab, col in zip(paths, labels, colors):
        xs, ys, zs, _ = zip(*path)
        base.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=col, width=6), opacity=0.85, name=lab))
        base.append(go.Scatter3d(x=[xs[0]], y=[ys[0]], z=[zs[0]], mode="markers",
            marker=dict(size=7, color=col, symbol="circle"),
            showlegend=False, hoverinfo="skip"))
    # frames: bola avanzando + estela
    n_zone = len(_zone_traces())
    frames = []
    for k in range(n_points):
        data = []
        for path, col in zip(paths, colors):
            xs, ys, zs, _ = zip(*path[:k+1])
            data.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                                     line=dict(color=col, width=6)))
            data.append(go.Scatter3d(x=[xs[-1]], y=[ys[-1]], z=[zs[-1]],
                mode="markers", marker=dict(size=9, color=col)))
        frames.append(go.Frame(data=data,
            traces=list(range(n_zone, n_zone+2*len(paths))), name=str(k)))
    fig = go.Figure(data=base, frames=frames)
    steps = [dict(method="animate", label=f"{k}",
                  args=[[str(k)], {"frame":{"duration":0,"redraw":True},
                                   "mode":"immediate"}]) for k in range(n_points)]
    fig.update_layout(
        title=title, height=620, margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", y=1.02),
        scene=dict(
            xaxis=dict(title="x (ft)", range=[-4, 4]),
            yaxis=dict(title="distancia (ft)", range=[56, -2]),
            zaxis=dict(title="altura (ft)", range=[0, 8]),
            aspectmode="manual", aspectratio=dict(x=1, y=3.2, z=1),
            camera=dict(eye=dict(x=0.0, y=-2.4, z=0.25),
                        center=dict(x=0, y=-0.25, z=-0.05)),
        ),
        updatemenus=[dict(type="buttons", showactive=False, y=0, x=0, xanchor="left",
            buttons=[
                dict(label="▶ Play", method="animate",
                     args=[None, {"frame":{"duration":28,"redraw":True},
                                  "fromcurrent":True,"transition":{"duration":0}}]),
                dict(label="⏸ Pausa", method="animate",
                     args=[[None], {"frame":{"duration":0,"redraw":False},
                                    "mode":"immediate"}]),
            ])],
        sliders=[dict(steps=steps, active=0, y=-0.02, x=0.12, len=0.85,
                      currentvalue=dict(prefix="frame "))],
    )
    return fig, metas


def _gif_bytes(rows, n_points=40, fps=24):
    """GIF vista-catcher (x,z) con profundidad simulada — para redes/reportes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    paths, labels, colors = [], [], []
    for i, (_, r) in enumerate(rows.iterrows()):
        try: paths.append(compute_pitch_path(r, n_points=n_points))
        except ValueError: continue
        labels.append(_pitch_label(r)); colors.append(PALETTE[i % len(PALETTE)])
    if not paths: return None
    y_max = max(p[0][1] for p in paths)
    frames = []
    for k in range(n_points):
        fig, ax = plt.subplots(figsize=(5.4, 6.0), dpi=90)
        ax.set_xlim(-3.2, 3.2); ax.set_ylim(0, 6.5)
        ax.add_patch(plt.Rectangle((-ZONE_X, ZONE_LO), 2*ZONE_X, ZONE_HI-ZONE_LO,
                                   fill=False, ec="#555", lw=1.6))
        ax.fill([-0.71,-0.71,0,0.71,0.71],[0.4,0.2,0.05,0.2,0.4],color="#bbb",alpha=.5)
        for path, lab, col in zip(paths, labels, colors):
            xs=[p[0] for p in path[:k+1]]; zs=[p[2] for p in path[:k+1]]
            depth = path[k][1]/y_max
            ax.plot(xs, zs, color=col, lw=1.4, alpha=0.45)
            ax.scatter([xs[-1]],[zs[-1]], s=30+260*(1-depth), color=col,
                       edgecolors="white", zorder=5, label=lab)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_visible(False)
        ax.legend(loc="upper right", fontsize=7, frameon=False)
        ax.set_title("Vista del catcher", fontsize=10)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight"); plt.close(fig)
        buf.seek(0); frames.append(Image.open(buf).convert("P"))
    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:],
                   duration=int(1000/fps), loop=0)
    return out.getvalue()


def _pick_pitches_ui(sub, key, max_n=6):
    """Selector de pitches a superponer (default: el más rápido de cada tipo)."""
    sub = sub.reset_index(drop=True)
    opts = {f'{r["PitchUID"]} — {_pitch_label(r)}'
            + (f' ({r["Date"].strftime("%b %d")})' if pd.notna(r.get("Date")) else ""): r["PitchUID"]
            for _, r in sub.iterrows()}
    defaults = []
    if "RelSpeed" in sub.columns:
        for _, g in sub.groupby("TaggedPitchType"):
            defaults.append(g.loc[g["RelSpeed"].idxmax(), "PitchUID"] if g["RelSpeed"].notna().any()
                            else g.iloc[0]["PitchUID"])
    default_keys = [k for k, v in opts.items() if v in defaults[:max_n]]
    chosen = st.multiselect(f"Pitches a superponer (máx {max_n})", list(opts.keys()),
                            default=default_keys[:max_n], key=key)
    ids = [opts[c] for c in chosen][:max_n]
    return sub[sub["PitchUID"].isin(ids)]


def render_trajectory_mode(df, lmeta):
    st.markdown('<div class="sh">🎯 Trayectorias de Pitcheo — 3D</div>', unsafe_allow_html=True)
    schema = validate_schema(df)
    if not schema["trajectory_ready"]:
        st.error("El dataset no tiene las columnas mínimas para trayectorias "
                 f"(faltan: {schema['missing_required'] or 'break vertical'}). "
                 "Se requiere RelSpeed, PlateLocSide/Height y HorzBreak + "
                 "InducedVertBreak (o VertBreak).")
        return
    df, phys_report = validate_physical(df)
    df = ensure_pitch_ids(df)
    if phys_report:
        with st.expander(f"⚠️ Validación física: {sum(phys_report.values())} lecturas "
                         "fuera de rango (marcadas como inválidas)"):
            st.json(phys_report)
    if schema["has_9p_kinematics"]:
        st.caption("📡 Paquete 9P detectado — trayectorias integradas de datos kinemáticos reales.")

    if "Pitcher" not in df.columns or df["Pitcher"].dropna().empty:
        st.error("No hay columna 'Pitcher'."); return
    pitchers = sorted(df["Pitcher"].dropna().unique())
    c1, c2, c3, c4 = st.columns([2,1.4,1,1])
    with c1: pitcher = st.selectbox("Pitcher", pitchers, key="tj_pitcher")
    pdf = df[df["Pitcher"] == pitcher].copy()
    with c2:
        pts = sorted(pdf["TaggedPitchType"].dropna().unique())
        sel_pt = st.multiselect("Tipos", pts, default=pts, key="tj_pt")
        if sel_pt: pdf = pdf[pdf["TaggedPitchType"].isin(sel_pt)]
    with c3:
        if "Balls" in pdf.columns and "Strikes" in pdf.columns and pdf["Balls"].notna().any():
            counts = ["Todos"]+sorted({f"{int(b)}-{int(s)}" for b,s in
                       zip(pdf["Balls"].dropna(), pdf["Strikes"].dropna())})
            cnt = st.selectbox("Conteo", counts, key="tj_cnt")
            if cnt != "Todos":
                b, s = map(int, cnt.split("-"))
                pdf = pdf[(pdf["Balls"]==b)&(pdf["Strikes"]==s)]
    with c4:
        if "BatterSide" in pdf.columns and pdf["BatterSide"].notna().any():
            side = st.selectbox("Bateador", ["Ambos","Right","Left"], key="tj_side")
            if side != "Ambos":
                pdf = pdf[pdf["BatterSide"].astype(str).str.startswith(side[0])]
    if "PitchCall" in pdf.columns:
        res = st.radio("Resultado", ["Todos","Strike","Bola","In Play"],
                       horizontal=True, key="tj_res")
        pc = pdf["PitchCall"].astype(str)
        if res=="Strike": pdf = pdf[pc.isin(["StrikeCalled","StrikeSwinging"])]
        elif res=="Bola": pdf = pdf[pc.isin(["BallCalled","BallinDirt","IntentionalBall"])]
        elif res=="In Play": pdf = pdf[pc.eq("InPlay")]
    if pdf.empty:
        st.warning("Sin pitches con esos filtros."); return

    tabs = st.tabs(["🎬 Vista 3D","🆚 Comparar pitchers","🔥 Heatmap ubicación",
                    "💥 Break chart","🎯 Release","📈 Tendencias"])

    # ── 🎬 Vista 3D ────────────────────────────────────────────────────────
    with tabs[0]:
        n_pts = st.slider("Puntos de interpolación", 20, 120, 50, 10, key="tj_np")
        sel = _pick_pitches_ui(pdf, "tj_pick")
        if sel.empty:
            st.info("Selecciona al menos un pitch.")
        else:
            fig, metas = build_3d_figure(sel, n_points=n_pts,
                                         title=f"{pitcher} — vista detrás del catcher")
            if fig is None:
                st.warning("No se pudo reconstruir ninguna trayectoria (datos faltantes).")
            else:
                st.plotly_chart(fig, use_container_width=True)
                if metas:
                    mdf = pd.DataFrame(metas)
                    mdf.insert(0, "Pitch", [_pitch_label(r) for _, r in sel.iterrows()][:len(mdf)])
                    st.dataframe(mdf, use_container_width=True, hide_index=True)
                e1, e2 = st.columns(2)
                with e1:
                    st.download_button("⬇️ Exportar HTML interactivo",
                        fig.to_html(include_plotlyjs="cdn").encode(),
                        f"{pitcher}_trayectorias.html", "text/html")
                with e2:
                    if st.button("🎞️ Generar GIF slow-mo (redes)", key="tj_gif",
                                 help="Anima el lanzamiento PROMEDIO de cada tipo de "
                                      "pitcheo (con los filtros actuales) sobre campo "
                                      "real, con spin realista — 900×900 para redes"):
                        from .social_render import render_social_gif
                        with st.spinner("Renderizando GIF cinematográfico… (~20s)"):
                            gif = render_social_gif(pdf, pitcher=pitcher)
                        if gif:
                            st.image(gif)
                            st.download_button("⬇️ Descargar GIF", gif,
                                f"{pitcher}_slowmo.gif", "image/gif", key="tj_gif_dl")
                        else:
                            st.warning("Datos insuficientes para el GIF.")

    # ── 🆚 Comparar pitchers ───────────────────────────────────────────────
    with tabs[1]:
        cA, cB = st.columns(2)
        with cA: p1 = st.selectbox("Pitcher A", pitchers, key="tj_pA")
        with cB: p2 = st.selectbox("Pitcher B", pitchers,
                                    index=min(1, len(pitchers)-1), key="tj_pB")
        for col, p in ((cA, p1), (cB, p2)):
            with col:
                sub = df[df["Pitcher"]==p]
                best = (sub.loc[sub.groupby("TaggedPitchType")["RelSpeed"].idxmax().dropna()]
                        if "RelSpeed" in sub.columns and sub["RelSpeed"].notna().any()
                        else sub.head(4))
                figp, _ = build_3d_figure(best.head(5), n_points=40, title=p)
                if figp is not None:
                    figp.update_layout(height=480)
                    st.plotly_chart(figp, use_container_width=True)
                else:
                    st.info(f"Sin datos de trayectoria para {p}.")

    # ── 🔥 Heatmap por tipo y conteo ───────────────────────────────────────
    with tabs[2]:
        loc = pdf.dropna(subset=["PlateLocSide","PlateLocHeight"])
        if loc.empty:
            st.info("Sin datos de ubicación.")
        else:
            fig_h = px.density_heatmap(loc, x="PlateLocSide", y="PlateLocHeight",
                facet_col="TaggedPitchType", facet_col_wrap=3,
                nbinsx=18, nbinsy=18, color_continuous_scale="RdYlBu_r",
                range_x=[-2.5,2.5], range_y=[0,5])
            for i in range(len(loc["TaggedPitchType"].unique())):
                fig_h.add_shape(type="rect", x0=-ZONE_X, x1=ZONE_X, y0=ZONE_LO, y1=ZONE_HI,
                                line=dict(color="#333", width=2),
                                row=(i // 3)+1, col=(i % 3)+1)
            fig_h.update_layout(height=420*max(1,int(np.ceil(loc["TaggedPitchType"].nunique()/3))),
                                coloraxis_showscale=False)
            st.plotly_chart(fig_h, use_container_width=True)

    # ── 💥 Break chart ─────────────────────────────────────────────────────
    with tabs[3]:
        prof = movement_profile(df, pitcher)
        if not prof["pitches"]:
            st.info("Sin datos de break.")
        else:
            pp = pd.DataFrame(prof["pitches"])
            fig_b = px.scatter(pp, x="hb", y="vb", color="pitch_type",
                               hover_data=["velo"], opacity=0.55,
                               color_discrete_map=STATCAST_COLORS,
                               color_discrete_sequence=PALETTE,
                               labels={"hb":"Horizontal Break (in)","vb":"Vertical Break (in)"})
            cc = pd.DataFrame(prof["centroids"])
            fig_b.add_trace(go.Scatter(x=cc["hb"], y=cc["vb"], mode="markers+text",
                text=cc["pitch_type"], textposition="top center",
                marker=dict(size=16, color="#111", symbol="x"), name="promedio"))
            fig_b.add_hline(y=0, line_color="#999"); fig_b.add_vline(x=0, line_color="#999")
            fig_b.update_layout(height=520, title=f"Movement profile — {pitcher}")
            st.plotly_chart(fig_b, use_container_width=True)

    # ── 🎯 Release consistency ─────────────────────────────────────────────
    with tabs[4]:
        rc = release_consistency(df, pitcher)
        if not rc["points"]:
            st.info("Sin RelHeight/RelSide.")
        else:
            s = rc["summary"]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Pitches", s["n"]); m2.metric("σ lateral", f'{s["std_side"]} ft')
            m3.metric("σ altura", f'{s["std_height"]} ft')
            m4.metric("Drift 1ª→última", f'{s["drift_first_to_last_ft"]} ft'
                      if s["drift_first_to_last_ft"] is not None else "—")
            rp = pd.DataFrame(rc["points"])
            fig_r = px.scatter(rp, x="rel_side", y="rel_height",
                               color="date" if rp["date"].notna().any() else "pitch_type",
                               symbol="pitch_type", opacity=0.65,
                               labels={"rel_side":"Release Side (ft)","rel_height":"Release Height (ft)"})
            fig_r.update_layout(height=500, title="Punto de release por fecha "
                                "(drift sostenido ⇒ fatiga o cambio mecánico)")
            st.plotly_chart(fig_r, use_container_width=True)
            if rc["by_date"]:
                st.dataframe(pd.DataFrame(rc["by_date"]), use_container_width=True, hide_index=True)

    # ── 📈 Tendencias velo/spin ────────────────────────────────────────────
    with tabs[5]:
        tr = velocity_spin_trends(df, pitcher)
        if not tr["outings"]:
            st.info("Se requieren fechas válidas.")
        else:
            td = pd.DataFrame(tr["outings"])
            for metric, lbl in (("avg_velo","Velocidad promedio (mph)"),
                                ("avg_spin","Spin promedio (rpm)")):
                if metric in td.columns:
                    fig_t = px.line(td, x="date", y=metric, color="pitch_type",
                                    markers=True, color_discrete_map=STATCAST_COLORS,
                                    color_discrete_sequence=PALETTE,
                                    labels={metric:lbl,"date":"Outing"})
                    fig_t.update_layout(height=340, title=lbl)
                    st.plotly_chart(fig_t, use_container_width=True)
            st.caption("Caída sostenida de velo/spin entre outings ⇒ señal de fatiga; "
                       "subida ⇒ progreso físico o mecánico.")

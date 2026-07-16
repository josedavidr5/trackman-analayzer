"""
trajectory.social_render — GIF cinematográfico "slow-motion" para redes sociales.

Vista del catcher con campo de béisbol en perspectiva, cada lanzamiento como
una pelota real (costuras rojas que rotan según SpinRate/SpinAxis), pitches en
secuencia con estela, marcador de resultado al cruzar el plato, y tarjeta
final con las métricas de cada lanzamiento. Salida cuadrada (900×900) lista
para Instagram / X / TikTok.

Uso:  render_social_gif(rows_df, pitcher="...", fps=30) -> bytes (GIF)
"""
from __future__ import annotations
import io
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, Arc, FancyBboxPatch, Rectangle, Polygon
from PIL import Image

from .engine import compute_pitch_path, pitch_metrics

# ── Cámara (umpire-cam: detrás y arriba del catcher) ─────────────────────────
CAM_Y, CAM_Z, F = -14.0, 4.2, 12.0
XLIM = (-2.6, 2.6); YLIM = (-3.45, 1.75)      # ventana cuadrada 5.2×5.2
BALL_R_FT = 0.121
BALL_VIS = 1.75                                # factor de visibilidad de la pelota
SLOWMO_SPIN = 8.0                              # divisor visual del spin (slow-mo)
ZONE_X, ZONE_LO, ZONE_HI = 0.83, 1.5, 3.5

PALETTE = ["#1f77b4","#d62728","#2ca02c","#ff7f0e","#9467bd","#8c564b"]
STATCAST_COLORS={
    "4-Seam":"#D22D49","Fastball":"#D22D49","Four-Seam Fastball":"#D22D49",
    "2-Seam":"#DE6A04","Sinker":"#FE9D00","Cutter":"#933F2C","Slider":"#C3BD0E",
    "Sweeper":"#DDB33A","Curve":"#00D1ED","Curveball":"#00D1ED",
    "Change":"#1DBE3A","Changeup":"#1DBE3A","Split":"#3BACAC",
    "Knuckleball":"#3C44CD","Screwball":"#60DB33",
}
def _pt_color(pt, idx=0):
    return STATCAST_COLORS.get(str(pt), PALETTE[idx % len(PALETTE)])
GRASS_A, GRASS_B = "#3e7c3a", "#468a41"
DIRT = "#b98a5a"; DIRT_DARK = "#a97b4e"
SKY_TOP, SKY_BOT = "#8ec9e8", "#dceef7"
WALL = "#274e2b"
# Paleta nocturna (partido de noche, look broadcast oscuro)
GRASS_A_N, GRASS_B_N = "#123219", "#173d20"
DIRT_N, DIRT_DARK_N = "#5a3f28", "#493320"
SKY_TOP_N, SKY_BOT_N = "#05070d", "#16233b"     # cenit negro → horizonte azul tenue
WALL_N = "#0d2213"

RESULT_ES = {"StrikeCalled":"Strike cantado","StrikeSwinging":"Swing y falla",
             "BallCalled":"Bola","BallinDirt":"Bola (tierra)","FoulBall":"Foul",
             "FoulBallFieldable":"Foul","FoulBallNotFieldable":"Foul",
             "InPlay":"En juego","HitByPitch":"Golpeado"}


def _proj(x, y, z):
    d = max(y - CAM_Y, 0.6)
    return F*x/d, F*(z - CAM_Z)/d


def _ball_r(y):
    return BALL_VIS*F*BALL_R_FT/max(y - CAM_Y, 0.6)


def _draw_field(ax, night=False):
    """Campo en perspectiva: cielo, barda, grama con franjas, tierra, montículo.
    night=True → paleta nocturna (fondo oscuro, líneas claras)."""
    if night:
        g_a, g_b, dirt, dirt_dark, wall = GRASS_A_N, GRASS_B_N, DIRT_N, DIRT_DARK_N, WALL_N
        sky_bot, sky_top = SKY_BOT_N, SKY_TOP_N
        line_c, plate_c, plate_edge, rubber_c, zone_c = "#e8eef6", "#e2e8ef", "#9fb0c0", "#eef2f6", "#ffffff"
    else:
        g_a, g_b, dirt, dirt_dark, wall = GRASS_A, GRASS_B, DIRT, DIRT_DARK, WALL
        sky_bot, sky_top = SKY_BOT, SKY_TOP
        line_c, plate_c, plate_edge, rubber_c, zone_c = "#f5f5f5", "#fafafa", "#888888", "#f2f2f2", "#111111"
    # cielo con gradiente
    grad = np.linspace(0, 1, 120).reshape(-1, 1)
    ax.imshow(grad, extent=[XLIM[0], XLIM[1], 0.0, YLIM[1]], origin="lower",
              cmap=matplotlib.colors.LinearSegmentedColormap.from_list("sky", [sky_bot, sky_top]),
              aspect="auto", zorder=0)
    # barda del outfield
    v_wall_base = F*(0.0-CAM_Z)/(400-CAM_Y); v_wall_top = F*(9.0-CAM_Z)/(400-CAM_Y)
    ax.add_patch(Rectangle((XLIM[0], v_wall_base), XLIM[1]-XLIM[0],
                           v_wall_top-v_wall_base, color=wall, zorder=1))
    # grama con franjas (bandas de y proyectadas)
    edges = [14, 22, 32, 46, 66, 96, 140, 220, 400]
    for i in range(len(edges)-1):
        v1 = F*(0-CAM_Z)/(edges[i]-CAM_Y); v2 = F*(0-CAM_Z)/(edges[i+1]-CAM_Y)
        ax.add_patch(Rectangle((XLIM[0], v1), XLIM[1]-XLIM[0], v2-v1,
                     color=g_a if i % 2 else g_b, zorder=1))
    # tierra frontal (círculo del home)
    v_home = F*(0-CAM_Z)/(14-CAM_Y)
    ax.add_patch(Rectangle((XLIM[0], YLIM[0]), XLIM[1]-XLIM[0],
                           v_home-YLIM[0], color=dirt, zorder=2))
    # círculo de tierra del montículo
    y_n, y_f = 50.0, 68.0
    v_n = F*(0-CAM_Z)/(y_n-CAM_Y); v_f = F*(0-CAM_Z)/(y_f-CAM_Y)
    u_half = F*13.0/(59.0-CAM_Y)
    ax.add_patch(mpatches.Ellipse((0, (v_n+v_f)/2), 2*u_half, (v_f-v_n), color=dirt, zorder=2))
    # lomita + goma
    u_m = F*4.5/(59.0-CAM_Y)
    ax.add_patch(mpatches.Ellipse((0, (v_n+v_f)/2+0.012), 2*u_m, 0.05, color=dirt_dark, zorder=3))
    ux, vy = _proj(0, 60.5, 0.85)
    ax.add_patch(Rectangle((ux-0.045, vy-0.006), 0.09, 0.012, color=rubber_c, zorder=4))
    # líneas de foul (desde las esquinas del plato, a 45°)
    for sgn in (1, -1):
        ts = np.linspace(0.0, 90, 60)
        pts = [_proj(sgn*(0.71+t), 1.417+t, 0) for t in ts]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=line_c, lw=2.4, alpha=0.9, zorder=3)
    # plato (pentágono)
    plate = [(-0.71, 1.417), (0.71, 1.417), (0.71, 0.9), (0, 0.45), (-0.71, 0.9)]
    ax.add_patch(Polygon([_proj(px, py, 0.001) for px, py in plate],
                         closed=True, facecolor=plate_c, edgecolor=plate_edge, lw=1.2, zorder=4))
    # cajas de bateo (bordes internos visibles)
    for sgn in (1, -1):
        seg = [_proj(sgn*1.21, yy, 0.001) for yy in np.linspace(0.6, 4.5, 12)]
        ax.plot([p[0] for p in seg], [p[1] for p in seg], color=line_c, lw=2.0, alpha=0.7, zorder=4)
    # zona de strike
    u_z = F*ZONE_X/(1.417-CAM_Y)
    v_lo = F*(ZONE_LO-CAM_Z)/(1.417-CAM_Y); v_hi = F*(ZONE_HI-CAM_Z)/(1.417-CAM_Y)
    ax.add_patch(Rectangle((-u_z, v_lo), 2*u_z, v_hi-v_lo, fill=False,
                           edgecolor=zone_c, lw=2.4, alpha=0.9, zorder=6))
    for f_ in (1/3, 2/3):
        ax.plot([-u_z+2*u_z*f_]*2, [v_lo, v_hi], color=zone_c, lw=0.8, alpha=0.4, zorder=6)
        ax.plot([-u_z, u_z], [v_lo+(v_hi-v_lo)*f_]*2, color=zone_c, lw=0.8, alpha=0.4, zorder=6)


# Curva real de la costura de una pelota de béisbol sobre la esfera unitaria
# (familia "tennis-ball curve": normalizar (cos t, sin t, c·sin 2t))
_T = np.linspace(0, 2*np.pi, 220)
_SEAM3D = np.stack([np.cos(_T), np.sin(_T), 0.8*np.sin(2*_T)])
_SEAM3D = _SEAM3D/np.linalg.norm(_SEAM3D, axis=0)


def _rot_matrix(axis, deg):
    a = np.asarray(axis, float); a = a/np.linalg.norm(a)
    th = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th)*K + (1-math.cos(th))*(K@K)


def _plot_seam(ax, X, Y, mask, lw, color, alpha, zorder):
    """Dibuja los tramos contiguos de la costura donde mask=True."""
    idx = np.where(mask)[0]
    if idx.size == 0: return
    splits = np.where(np.diff(idx) > 1)[0]
    for seg in np.split(idx, splits+1):
        if seg.size >= 2:
            ax.plot(X[seg], Y[seg], color=color, lw=lw, alpha=alpha,
                    zorder=zorder, solid_capstyle="round")


def _draw_ball(ax, u, v, r, spin_deg, axis_deg, blur_from=None):
    """
    Pelota de béisbol realista: esfera blanca con la costura auténtica en 3D,
    rotada según SpinRate/SpinAxis y proyectada — se ve girar en slow motion.
    """
    if blur_from is not None:
        ax.plot([blur_from[0], u], [blur_from[1], v], color="#ffffff",
                lw=max(1.2, r*110), alpha=0.25,
                solid_capstyle="round", zorder=8)
    ax.add_patch(Circle((u+r*0.13, v-r*0.13), r, color="#00000022", zorder=9))
    ball = Circle((u, v), r, facecolor="#fbfbf4", edgecolor="#b6b6ac",
                  lw=max(0.3, r*5), zorder=10)
    ax.add_patch(ball)
    # sombreado esférico (media luna inferior-derecha)
    shade = Circle((u+r*0.30, v-r*0.30), r*0.92, color="#00000010", zorder=10.5)
    shade.set_clip_path(ball)
    ax.add_patch(shade)
    # costura 3D: eje de spin en pantalla (con leve inclinación hacia cámara
    # para que la rotación siempre sea perceptible)
    ax_rad = math.radians(axis_deg)
    spin_axis = (math.cos(ax_rad), math.sin(ax_rad), 0.35)
    R = _rot_matrix(spin_axis, spin_deg)
    P = R @ _SEAM3D
    X, Y, Z = u + r*P[0]*0.98, v + r*P[1]*0.98, P[2]
    lw = max(0.6, r*22)
    _plot_seam(ax, X, Y, Z <= 0.02, lw*0.85, "#e8b7ae", 0.35, 10.7)  # cara oculta
    _plot_seam(ax, X, Y, Z > 0.02, lw, "#b7352a", 1.0, 11)           # cara visible
    # brillo
    ax.add_patch(Circle((u-r*0.38, v+r*0.38), r*0.16, color="#ffffff",
                        alpha=0.65, zorder=12))


def _fmt(v, suf="", dec=1):
    try:
        f = float(v)
        if math.isnan(f): return "—"
        return f"{f:.{dec}f}{suf}"
    except (TypeError, ValueError):
        return "—"


AVG_COLS = ["RelSpeed","SpinRate","SpinAxis","RelHeight","RelSide","Extension",
            "HorzBreak","InducedVertBreak","VertBreak","PlateLocSide","PlateLocHeight"]
STRIKE_CALLS = {"StrikeCalled","StrikeSwinging","FoulBall","FoulBallFieldable",
                "FoulBallNotFieldable","InPlay"}


def average_pitches(df: pd.DataFrame, max_types: int = 5) -> pd.DataFrame:
    """
    Un lanzamiento REPRESENTATIVO por tipo: el promedio de todas las métricas
    del pitcher (velo, spin, release, break, ubicación). Incluye _n (muestras)
    y _strike_pct para mostrar en la etiqueta y la tarjeta final.
    """
    rows = []
    for pt, g in df.groupby("TaggedPitchType"):
        if str(pt) in ("Unknown","nan",""): continue
        r = {"TaggedPitchType": str(pt), "_n": int(len(g))}
        for c in AVG_COLS:
            if c in g.columns and g[c].notna().any():
                r[c] = float(g[c].mean())
        if "PitchCall" in g.columns:
            pc = g["PitchCall"].astype(str)
            r["_strike_pct"] = round(100.0*pc.isin(STRIKE_CALLS).sum()/len(g), 0)
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty: return out
    return out.sort_values("_n", ascending=False).head(max_types).reset_index(drop=True)


def _result_text(row):
    n = row.get("_n")
    if n is not None and not (isinstance(n, float) and math.isnan(n)):
        sp = row.get("_strike_pct")
        sp_txt = f" · Strike {sp:.0f}%" if sp is not None and not (
            isinstance(sp, float) and math.isnan(sp)) else ""
        return f"promedio de {int(n)} pitches{sp_txt}"
    pr = str(row.get("PlayResult", "") or "")
    pc = str(row.get("PitchCall", "") or "")
    if pr not in ("", "nan", "—", "Undefined", "None"):
        return pr
    return RESULT_ES.get(pc, pc if pc not in ("", "nan") else "—")


def _fig_to_pil(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _fig_png_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_trajectories_png(rows: pd.DataFrame, pitcher: str = "", night: bool = True):
    """Render estático realista (matplotlib) de TODAS las trayectorias sobre el campo en
    perspectiva (catcher view). Cada pitcheo = cinta de color con glow + pelota con anillo al
    cruzar el plato. Devuelve (png_bytes, [metrics...]) o (None, []) si no hay trayectorias."""
    items = []
    for i, (_, r) in enumerate(rows.iterrows()):
        try:
            p = compute_pitch_path(r, n_points=46)
        except ValueError:
            continue
        items.append((p, _pt_color(r.get("TaggedPitchType"), i), pitch_metrics(r)))
    if not items:
        return None, []
    fig, ax = _new_canvas()
    _draw_field(ax, night=night)
    _header(ax, (pitcher.strip() or "TRACKMAN"), "PITCH TRAJECTORIES · vista del catcher")
    for p, col, _m in items:
        us = [_proj(x, y, z)[0] for (x, y, z, _t) in p]
        vs = [_proj(x, y, z)[1] for (x, y, z, _t) in p]
        ax.plot(us, vs, color=col, lw=10, alpha=0.20, solid_capstyle="round", zorder=7)
        ax.plot(us, vs, color=col, lw=3.4, alpha=0.98, solid_capstyle="round", zorder=8)
        xf, yf, zf, _ = p[-1]
        uf, vf = _proj(xf, yf, zf)
        _draw_ball(ax, uf, vf, _ball_r(yf), 0.0, 0.0)
        ax.add_patch(Circle((uf, vf), _ball_r(yf) * 1.7, fill=False,
                            edgecolor=col, lw=2.6, zorder=13))
    return _fig_png_bytes(fig), [it[2] for it in items]


def _new_canvas(bg_img=None):
    fig = plt.figure(figsize=(9, 9), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*XLIM); ax.set_ylim(*YLIM)
    ax.axis("off")
    if bg_img is not None:
        ax.imshow(bg_img, extent=[XLIM[0], XLIM[1], YLIM[0], YLIM[1]],
                  aspect="auto", zorder=0, interpolation="bilinear")
    return fig, ax


def _header(ax, title, sub):
    ax.text(0.03, 0.975, title, transform=ax.transAxes, fontsize=21,
            fontweight="bold", color="#ffffff", va="top",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="#00000088")])
    ax.text(0.03, 0.925, sub, transform=ax.transAxes, fontsize=12.5,
            color="#ffffff", va="top", alpha=0.95,
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground="#00000066")])


def render_social_gif(rows: pd.DataFrame, pitcher: str = "", fps: int = 30,
                      travel_frames: int = 30, hold_frames: int = 10,
                      endcard_frames: int = 36, use_average: bool = True,
                      night: bool = True) -> bytes | None:
    """
    GIF slow-motion para redes: el lanzamiento PROMEDIO de cada tipo de pitcheo
    (use_average=True, default) en secuencia sobre el campo, pelota de béisbol
    con spin realista, y tarjeta final con las métricas promedio de cada uno.
    Con use_average=False anima los pitches individuales recibidos.
    """
    import matplotlib.patheffects  # noqa: F401 (usado vía _header)
    if use_average:
        rows = average_pitches(rows)
        if rows.empty: return None
    pitches = []
    for i, (_, r) in enumerate(rows.iterrows()):
        try:
            path = compute_pitch_path(r, n_points=travel_frames)
        except ValueError:
            continue
        pitches.append({"row": r, "path": path, "metrics": pitch_metrics(r),
                        "color": _pt_color(r.get("TaggedPitchType"), i),
                        "label": str(r.get("TaggedPitchType", "Pitch"))})
    if not pitches:
        return None

    # fondo renderizado una sola vez
    fig_bg, ax_bg = _new_canvas()
    _draw_field(ax_bg, night=night)
    bg = np.asarray(_fig_to_pil(fig_bg))

    title = f"{pitcher}".strip() or "TRACKMAN"
    frames = []      # [(PIL.Image, duración_ms)] — frames únicos con duración propia
    FRAME_MS = int(1000/fps)

    landed = []   # [(u,v,color,texto)]
    for p in pitches:
        row, path, met = p["row"], p["path"], p["metrics"]
        spin = float(row.get("SpinRate") or 2200.0)
        axis = float(row.get("SpinAxis") or 200.0) - 180.0
        t_f = met["flight_time"]
        deg_per_frame = min(25.0, (spin/60.0)*360.0*(t_f/travel_frames)/SLOWMO_SPIN)
        velo = _fmt(row.get("RelSpeed"), " mph")
        n_avg = row.get("_n")
        avg_tag = (f" · promedio n={int(n_avg)}"
                   if n_avg is not None and not (isinstance(n_avg, float) and math.isnan(n_avg)) else "")
        sub = f"{p['label']} · {velo} · {_fmt(spin,' rpm',0)}{avg_tag} · SLOW-MO"
        prev_uv = None
        for k in range(travel_frames):
            fig, ax = _new_canvas(bg)
            _header(ax, title, sub)
            # marcadores de pitches anteriores
            for (lu, lv, lc, _txt) in landed:
                ax.add_patch(Circle((lu, lv), 0.14, fill=False,
                                    edgecolor=lc, lw=2.4, alpha=0.9, zorder=7))
            # estela del pitch actual (cola difuminada, no burbujas)
            trail = path[max(0, k-9):k]
            nt = len(trail)
            for j, (tx, ty, tz, _tt) in enumerate(trail):
                tu, tv = _proj(tx, ty, tz)
                fade = (j+1)/max(nt, 1)
                ax.add_patch(Circle((tu, tv), _ball_r(ty)*(0.30+0.35*fade),
                                    color=p["color"], lw=0,
                                    alpha=0.05+0.12*fade, zorder=7))
            x, y, z, _t = path[k]
            u, v = _proj(x, y, z)
            _draw_ball(ax, u, v, _ball_r(y), k*deg_per_frame, axis,
                       blur_from=prev_uv if k else None)
            prev_uv = (u, v)
            frames.append((_fig_to_pil(fig), FRAME_MS))
        # hold: UN frame largo con el resultado del pitch (PIL fusiona
        # frames idénticos, así que la pausa se logra con duración, no repitiendo)
        xf, yf, zf, _ = path[-1]
        uf, vf = _proj(xf, yf, zf); rf = _ball_r(yf)
        res = _result_text(row)
        landed.append((uf, vf, p["color"], res))
        fig, ax = _new_canvas(bg)
        _header(ax, title, sub)
        for (lu, lv, lc, _txt) in landed[:-1]:
            ax.add_patch(Circle((lu, lv), 0.14, fill=False,
                                edgecolor=lc, lw=2.4, alpha=0.9, zorder=7))
        _draw_ball(ax, uf, vf, rf, travel_frames*deg_per_frame, axis)
        ax.add_patch(Circle((uf, vf), rf*1.7, fill=False,
                            edgecolor=p["color"], lw=3.0, zorder=13))
        tag = f"{p['label']} · {velo} · {res}"
        ax.text(uf, vf-rf*3.4, tag, ha="center", fontsize=13,
                fontweight="bold", color="#ffffff", zorder=14,
                bbox=dict(boxstyle="round,pad=0.45",
                          facecolor=p["color"], edgecolor="none", alpha=0.93))
        frames.append((_fig_to_pil(fig), hold_frames*FRAME_MS))

    # ── tarjeta final de métricas ────────────────────────────────────────
    fig, ax = _new_canvas(bg)
    for (lu, lv, lc, _txt) in landed:
        ax.add_patch(Circle((lu, lv), 0.14, fill=False,
                            edgecolor=lc, lw=2.4, alpha=0.8, zorder=7))
    ax.add_patch(FancyBboxPatch((0.06, 0.08), 0.88, 0.84,
                 transform=ax.transAxes, boxstyle="round,pad=0.015",
                 facecolor="#0d1b2acc", edgecolor="#ffffff33", lw=1.5, zorder=20))
    ax.text(0.5, 0.86, title, transform=ax.transAxes, ha="center",
            fontsize=22, fontweight="bold", color="#ffffff", zorder=21)
    subtitle_card = ("PROMEDIO POR TIPO DE LANZAMIENTO" if use_average
                     else "RESUMEN DE LANZAMIENTOS")
    ax.text(0.5, 0.815, subtitle_card, transform=ax.transAxes,
            ha="center", fontsize=11, color="#8ea8c3", zorder=21)
    n = len(pitches)
    row_h = min(0.145, 0.62/n)
    for i, p in enumerate(pitches):
        r, met = p["row"], p["metrics"]
        y0 = 0.75 - i*row_h
        ax.add_patch(Circle((0.115, y0-0.012), 0.016, transform=ax.transAxes,
                            color=p["color"], zorder=22))
        ax.text(0.15, y0, f"{p['label']}  ·  {_fmt(r.get('RelSpeed'),' mph')}  ·  "
                f"{_fmt(r.get('SpinRate'),' rpm',0)}",
                transform=ax.transAxes, fontsize=14.5, fontweight="bold",
                color="#ffffff", va="center", zorder=22)
        ivb = r.get("InducedVertBreak", r.get("VertBreak"))
        inch = '"'
        det = (f"HB {_fmt(r.get('HorzBreak'), inch)}  ·  IVB {_fmt(ivb, inch)}  ·  "
               f"VAA {_fmt(met.get('vaa_deg'),'°')}  ·  "
               f"{_result_text(r)}")
        ax.text(0.15, y0-0.042, det, transform=ax.transAxes, fontsize=11,
                color="#b9cbdd", va="center", zorder=22)
    ax.text(0.5, 0.115, "Generado con Trackman Analytics", transform=ax.transAxes,
            ha="center", fontsize=9.5, color="#8ea8c3", alpha=0.8, zorder=21)
    frames.append((_fig_to_pil(fig), endcard_frames*FRAME_MS + 1500))

    out = io.BytesIO()
    imgs = [f.quantize(colors=220, method=Image.MEDIANCUT) for f, _ in frames]
    durs = [d for _, d in frames]
    imgs[0].save(out, format="GIF", save_all=True, append_images=imgs[1:],
                 duration=durs, loop=0, optimize=False)
    return out.getvalue()

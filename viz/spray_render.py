"""Spray chart broadcast: campo top-down foto-realista (matplotlib) + panel de bateo. PNG bytes."""
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp

GRASS_A, GRASS_B = "#3f8c3a", "#4a9a44"     # franjas de corte
DIRT, TRACK = "#b07a4a", "#c9a06a"
WALL = "#20361f"
RESULT_COLORS = {"1B": "#1DBE3A", "2B": "#00D1ED", "3B": "#9467bd", "HR": "#D22D49", "Out": "#8899a6"}


def _fence_xy(n=240):
    t = np.linspace(-45, 45, n)
    r = 330 + 70 * np.cos(np.deg2rad(t * 2))     # 330 en líneas, ~400 al CF
    return r * np.sin(np.deg2rad(t)), r * np.cos(np.deg2rad(t)), t, r


def render_spray_png(points, name="", color_by="ev"):
    pts = points.get("points", []) if points else []
    if not pts:
        return None
    fig = plt.figure(figsize=(8.6, 7.4), dpi=120)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0]); ax.set_axis_off()
    ax.set_xlim(-360, 360); ax.set_ylim(-40, 440); ax.set_aspect("equal")
    fx, fy, ft, fr = _fence_xy()
    # pasto (fan) con franjas de corte: cuñas radiales alternadas
    for i in range(len(ft) - 1):
        wedge = [(0, 0), (fx[i], fy[i]), (fx[i + 1], fy[i + 1])]
        ax.add_patch(mp.Polygon(wedge, closed=True, color=GRASS_A if i % 2 else GRASS_B, zorder=0, lw=0))
    # warning track (anillo tan por dentro de la barda)
    tx = (fr - 12) * np.sin(np.deg2rad(ft)); ty = (fr - 12) * np.cos(np.deg2rad(ft))
    ax.fill(np.concatenate([fx, tx[::-1]]), np.concatenate([fy, ty[::-1]]), color=TRACK, zorder=1, lw=0)
    # barda
    ax.plot(fx, fy, color=WALL, lw=4, zorder=2, solid_capstyle="round")
    # infield de tierra (arco skin) + montículo
    inf_t = np.linspace(-45, 45, 80)
    arc_x = 95 * np.sin(np.deg2rad(inf_t)); arc_y = 95 * np.cos(np.deg2rad(inf_t))
    ax.fill(np.concatenate([[0], arc_x, [0]]), np.concatenate([[0], arc_y, [0]]),
            color=DIRT, zorder=2, lw=0)
    ax.add_patch(mp.Circle((0, 60.5), 9, facecolor=DIRT, edgecolor="none", zorder=3))
    # líneas de foul, plato, bases
    d = 63.64
    for sgn in (1, -1):
        ax.plot([0, sgn * 330 * np.sin(np.deg2rad(45))], [0, 330 * np.cos(np.deg2rad(45))],
                color="#f2f2f2", lw=2.0, zorder=4)
    ax.add_patch(mp.Polygon([(-3.5, 0), (3.5, 0), (3.5, -3.5), (0, -7), (-3.5, -3.5)],
                 closed=True, facecolor="white", edgecolor="#cfcfcf", lw=1, zorder=5))
    for bx, by in [(d, d), (0, 2 * d), (-d, d)]:
        ax.add_patch(mp.Rectangle((bx - 3, by - 3), 6, 6, angle=45, facecolor="white",
                     edgecolor="#cfcfcf", lw=1, zorder=5))
    # batazos
    xs = [p["x"] for p in pts]; ys = [p["y"] for p in pts]
    if color_by == "result":
        for res, col in RESULT_COLORS.items():
            gx = [p["x"] for p in pts if p["result"] == res]
            gy = [p["y"] for p in pts if p["result"] == res]
            if gx:
                ax.scatter(gx, gy, s=70, color=col, alpha=0.9, edgecolors="white",
                           linewidths=0.8, zorder=7, label=res)
        other = [(p["x"], p["y"]) for p in pts if p["result"] not in RESULT_COLORS]
        if other:
            ax.scatter([o[0] for o in other], [o[1] for o in other], s=34, color="#dddddd",
                       alpha=0.5, edgecolors="white", linewidths=0.4, zorder=6)
        ax.legend(loc="lower right", fontsize=9, framealpha=0.85)
    else:
        evs = [p["ev"] if p["ev"] is not None else np.nan for p in pts]
        sc = ax.scatter(xs, ys, c=evs, cmap="coolwarm", vmin=65, vmax=112, s=70, alpha=0.9,
                        edgecolors="white", linewidths=0.8, zorder=7)
        cb = fig.colorbar(sc, ax=ax, pad=0.01, shrink=0.5)
        cb.set_label("Exit Velocity (mph)", fontsize=9); cb.outline.set_visible(False)
    ax.text(0, 415, "400 ft", fontsize=8, color="#7a8a99", ha="center", zorder=6)
    buf = io.BytesIO(); fig.savefig(buf, format="png", facecolor="#ffffff")
    plt.close(fig); buf.seek(0)
    return buf.getvalue()

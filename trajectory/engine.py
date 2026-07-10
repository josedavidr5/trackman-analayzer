"""
trajectory.engine — reconstrucción física de la trayectoria del pitcheo.

Sistema de coordenadas (vista del catcher):
    x : horizontal en ft (+ = derecha del catcher / lado del bateador zurdo)
    y : distancia al frente del plato en ft (release ≈ 54, plato = PLATE_Y)
    z : altura en ft

Dos modos de reconstrucción:
  1. KINEMÁTICO — si el CSV trae el paquete 9P de TrackMan
     (x0,y0,z0, vx0,vy0,vz0, ax0,ay0,az0): integra directamente el modelo de
     aceleración constante (gravedad + Magnus + drag ya incluidos en a).
  2. INFERIDO — si solo hay release/velocidad/break/ubicación (el caso típico
     de exports de torneos): resuelve las aceleraciones constantes que
     reproducen exactamente el punto de release, el break horizontal/vertical
     inducido y la ubicación en el plato reportados por TrackMan.

Ambos producen un camino (x,y,z,t) con N puntos y las mismas métricas
derivadas: tiempo de vuelo, VAA/HAA y spin efficiency estimada.
"""
from __future__ import annotations
import math

G = 32.174                 # ft/s²
PLATE_Y = 17.0/12.0        # frente del plato (17 in) — punto de medición de PlateLoc
RELEASE_DIST_TOTAL = 60.5  # ft, goma al vértice del plato
DEFAULT_EXTENSION = 6.0    # ft si falta Extension
DEFAULT_REL_HEIGHT = 5.8   # ft si falta RelHeight
MPH_TO_FPS = 5280.0/3600.0
# Física de la pelota (unidades imperiales, slugs/ft)
BALL_RADIUS_FT = 0.1208    # 2.9 in circunf 9.125in
BALL_MASS_SLUG = 0.01003   # 145 g
AIR_RHO = 0.0023           # slug/ft³ a nivel del mar
BALL_AREA_FT2 = math.pi*BALL_RADIUS_FT**2

_KIN_COLS = ("x0","y0","z0","vx0","vy0","vz0","ax0","ay0","az0")


def _num(row, *keys, default=None):
    """Primer valor numérico finito entre varios alias de columna."""
    for k in keys:
        v = row.get(k) if hasattr(row, "get") else getattr(row, k, None)
        try:
            f = float(v)
            if math.isfinite(f):
                return f
        except (TypeError, ValueError):
            continue
    return default


def has_kinematics(row) -> bool:
    return all(_num(row, c) is not None for c in _KIN_COLS)


def initial_conditions(row) -> dict:
    """
    Devuelve {x0,y0,z0,vx0,vy0,vz0,ax,ay,az,t_flight,source}.
    Lanza ValueError si no hay datos suficientes ni para el modo inferido.
    """
    if has_kinematics(row):
        kin = _try_kinematic(row)
        if kin is not None:
            return kin
        # 9P presente pero con convención/unidades distintas → modo inferido

    # ── Modo inferido ────────────────────────────────────────────────────
    v_mph = _num(row, "RelSpeed", "ReleaseSpeed")
    xf    = _num(row, "PlateLocSide")
    zf    = _num(row, "PlateLocHeight")
    if v_mph is None or xf is None or zf is None:
        raise ValueError("Faltan RelSpeed/PlateLocSide/PlateLocHeight y no hay paquete 9P")
    ext = _num(row, "Extension", default=DEFAULT_EXTENSION)
    x0  = _num(row, "RelSide", "ReleaseSide", default=0.0)
    z0  = _num(row, "RelHeight", "ReleaseHeight", default=DEFAULT_REL_HEIGHT)
    hb  = (_num(row, "HorzBreak", default=0.0) or 0.0)/12.0        # in → ft
    ivb = _num(row, "InducedVertBreak")
    if ivb is None:
        ivb = _num(row, "VertBreak", default=0.0)                  # aprox si no hay IVB
    ivb = (ivb or 0.0)/12.0

    y0 = RELEASE_DIST_TOTAL - ext
    D  = y0 - PLATE_Y
    v0 = v_mph*MPH_TO_FPS
    # La pelota pierde ~9% de velocidad goma→plato; velocidad media ≈ 0.955·v0
    t_f = D/(0.955*v0)
    vy0 = -v0
    ay  = 2.0*(-D - vy0*t_f)/t_f**2          # desaceleración por drag implícita

    # Objetivo "sin spin": ubicación observada menos el break inducido
    x_ns, z_ns = xf - hb, zf - ivb
    vx0 = (x_ns - x0)/t_f
    vz0 = (z_ns - z0 + 0.5*G*t_f**2)/t_f
    ax  = 2.0*hb/t_f**2                       # Magnus horizontal medio
    az  = -G + 2.0*ivb/t_f**2                 # gravedad + Magnus vertical
    return {"x0":x0,"y0":y0,"z0":z0,"vx0":vx0,"vy0":vy0,"vz0":vz0,
            "ax":ax,"ay":ay,"az":az,"t_flight":t_f,"source":"inferred"}


def _try_kinematic(row):
    """
    Integra el paquete 9P SOLO si es consistente: release y velocidad en
    rangos físicos (pies/fps) y, cuando hay PlateLoc, el punto de cruce del
    modelo debe coincidir con lo que reporta TrackMan (±0.75 ft). Si el CSV
    usa otra convención de ejes o unidades métricas, devolvemos None y el
    motor cae al modo inferido, que aterriza EXACTAMENTE en PlateLoc.
    """
    x0,y0,z0 = (_num(row,"x0"), _num(row,"y0"), _num(row,"z0"))
    vx,vy,vz = (_num(row,"vx0"), _num(row,"vy0"), _num(row,"vz0"))
    ax,ay,az = (_num(row,"ax0"), _num(row,"ay0"), _num(row,"az0"))
    if not (40.0 < y0 < 62.0):        return None   # release en ft desde el plato
    if not (-165.0 < vy < -70.0):     return None   # fps hacia el plato
    if not (0.0 < z0 < 9.0):          return None
    try:
        t_f = _solve_time_to_plate(y0, vy, ay)
    except ValueError:
        return None
    xf = x0 + vx*t_f + 0.5*ax*t_f*t_f
    zf = z0 + vz*t_f + 0.5*az*t_f*t_f
    px = _num(row, "PlateLocSide"); pz = _num(row, "PlateLocHeight")
    if px is not None and pz is not None:
        if abs(xf-px) > 0.75 or abs(zf-pz) > 0.75:
            return None                              # no cruza donde TrackMan midió
    return {"x0":x0,"y0":y0,"z0":z0,"vx0":vx,"vy0":vy,"vz0":vz,
            "ax":ax,"ay":ay,"az":az,"t_flight":t_f,"source":"kinematic"}


def _solve_time_to_plate(y0, vy0, ay):
    """Menor t>0 con y(t)=PLATE_Y bajo aceleración constante."""
    c = y0 - PLATE_Y
    if abs(ay) < 1e-9:
        if abs(vy0) < 1e-9:
            raise ValueError("Velocidad y aceleración nulas hacia el plato")
        t = -c/vy0
    else:
        disc = vy0*vy0 - 2.0*ay*c
        if disc < 0:
            raise ValueError("La trayectoria no alcanza el plato")
        r = math.sqrt(disc)
        candidates = [t for t in ((-vy0-r)/ay, (-vy0+r)/ay) if t > 1e-6]
        if not candidates:
            raise ValueError("Sin solución positiva de tiempo de vuelo")
        t = min(candidates)
    if not (0.05 < t < 2.5):
        raise ValueError(f"Tiempo de vuelo no físico: {t:.3f}s")
    return t


def compute_pitch_path(pitch_row, n_points: int = 50) -> list:
    """
    Reconstruye la trayectoria release→plato.
    Devuelve lista de tuplas (x, y, z, t) con n_points muestras equiespaciadas
    en el tiempo (default 50 — suficiente para animación suave a 30–60 fps).
    """
    if n_points < 2:
        raise ValueError("n_points debe ser ≥ 2")
    ic = initial_conditions(pitch_row)
    t_f = ic["t_flight"]
    pts = []
    for i in range(n_points):
        t = t_f*i/(n_points-1)
        x = ic["x0"] + ic["vx0"]*t + 0.5*ic["ax"]*t*t
        y = ic["y0"] + ic["vy0"]*t + 0.5*ic["ay"]*t*t
        z = ic["z0"] + ic["vz0"]*t + 0.5*ic["az"]*t*t
        pts.append((round(x,4), round(y,4), round(z,4), round(t,4)))
    return pts


def pitch_metrics(pitch_row) -> dict:
    """
    Métricas derivadas del modelo:
      flight_time (s), vaa_deg (ángulo vertical de aproximación, − = cayendo),
      haa_deg (horizontal, − = hacia el lado del guante del catcher izquierdo),
      plate_speed_mph, spin_efficiency (0–1, estimada; None sin SpinRate).
    """
    ic = initial_conditions(pitch_row)
    t = ic["t_flight"]
    vx_f = ic["vx0"] + ic["ax"]*t
    vy_f = ic["vy0"] + ic["ay"]*t
    vz_f = ic["vz0"] + ic["az"]*t
    vaa = math.degrees(math.atan2(vz_f, abs(vy_f)))
    haa = math.degrees(math.atan2(vx_f, abs(vy_f)))
    plate_speed = math.sqrt(vx_f**2+vy_f**2+vz_f**2)/MPH_TO_FPS
    eff = _spin_efficiency(pitch_row, ic)
    return {"flight_time": round(t,4), "vaa_deg": round(vaa,2),
            "haa_deg": round(haa,2), "plate_speed_mph": round(plate_speed,1),
            "spin_efficiency": eff, "model": ic["source"]}


def _spin_efficiency(row, ic) -> float | None:
    """
    Estimación de spin efficiency = spin transversal implícito por el
    movimiento / spin total medido. Aproximación tipo Nathan: invierte el
    coeficiente de lift CL = 1/(2.32 + 0.4/S) donde S = R·ω/v.
    Es una ESTIMACIÓN (sin drag separado no hay descomposición exacta).
    """
    spin = _num(row, "SpinRate")
    if not spin or spin <= 0:
        return None
    # Aceleración Magnus media (quitando gravedad del eje z)
    a_mx, a_mz = ic["ax"], ic["az"] + G
    a_m = math.sqrt(a_mx**2 + a_mz**2)
    v_avg = abs(ic["vy0"]) * 0.955
    cl = a_m*BALL_MASS_SLUG/(0.5*AIR_RHO*BALL_AREA_FT2*v_avg**2)
    cl = min(cl, 0.42)                     # saturación física del lift
    s = 0.4*cl/(1.0 - 2.32*cl) if cl < 1.0/2.32 else 1.5
    s = max(0.0, min(s, 1.5))
    omega = s*v_avg/BALL_RADIUS_FT         # rad/s
    spin_t = omega*60.0/(2.0*math.pi)      # rpm transversal implícito
    return round(max(0.0, min(spin_t/spin, 1.0)), 3)

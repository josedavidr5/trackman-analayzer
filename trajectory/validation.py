"""
trajectory.validation — schema y rangos físicos para detectar errores de
captura del dispositivo TrackMan (lecturas imposibles → NaN, no se descartan
filas completas).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# Campos del schema de trayectoria. required=el pipeline debe tenerlos;
# optional=se usan si existen (paquete 9P, ids).
REQUIRED_FIELDS = {
    "required": ["Pitcher","Batter","Date","TaggedPitchType","RelSpeed",
                 "RelHeight","RelSide","Extension","HorzBreak",
                 "PlateLocHeight","PlateLocSide","SpinRate","SpinAxis",
                 "Balls","Strikes"],
    "vertical_break_any_of": ["InducedVertBreak","VertBreak"],
    "optional_9p": ["x0","y0","z0","vx0","vy0","vz0","ax0","ay0","az0"],
    "optional_ids": ["PitchUID","PitcherId","BatterId"],
}

# Rangos físicos razonables (fuera de rango ⇒ error de captura ⇒ NaN)
PHYSICAL_RANGES = {
    "RelSpeed":        (40.0, 110.0),   # mph (amplio: HS→pro; spec pedía 60–105)
    "SpinRate":        (200.0, 3600.0), # rpm
    "SpinAxis":        (0.0, 360.0),    # grados
    "RelHeight":       (1.5, 8.0),      # ft
    "RelSide":         (-5.0, 5.0),
    "Extension":       (2.0, 8.5),
    "HorzBreak":       (-35.0, 35.0),   # in
    "InducedVertBreak":(-35.0, 35.0),
    "VertBreak":       (-80.0, 20.0),
    "PlateLocHeight":  (-2.5, 7.0),     # ft
    "PlateLocSide":    (-4.0, 4.0),
    "ExitSpeed":       (10.0, 125.0),   # mph
    "Angle":           (-90.0, 90.0),
    "Distance":        (0.0, 550.0),
    "vy0":             (-165.0, -55.0), # fps hacia el plato
    "ay0":             (0.0, 40.0),
    "az0":             (-60.0, 10.0),
}


def validate_schema(df: pd.DataFrame) -> dict:
    """Reporta qué campos del schema están presentes/faltantes."""
    cols = set(df.columns)
    missing = [c for c in REQUIRED_FIELDS["required"] if c not in cols]
    has_vert = any(c in cols for c in REQUIRED_FIELDS["vertical_break_any_of"])
    has_9p = all(c in cols for c in REQUIRED_FIELDS["optional_9p"])
    return {"missing_required": missing,
            "has_vertical_break": has_vert,
            "has_9p_kinematics": has_9p,
            "trajectory_ready": (not any(m in missing for m in
                ["RelSpeed","PlateLocHeight","PlateLocSide"])) and has_vert}


def validate_physical(df: pd.DataFrame) -> tuple:
    """
    Valores fuera de rango físico → NaN (error de captura del dispositivo).
    Devuelve (df_limpio, reporte) donde reporte = {columna: n_invalidos}.
    """
    df = df.copy()
    report = {}
    for col,(lo,hi) in PHYSICAL_RANGES.items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        bad = vals.notna() & ((vals < lo) | (vals > hi))
        n = int(bad.sum())
        if n:
            report[col] = n
            vals[bad] = np.nan
        df[col] = vals
    return df, report

"""
trajectory.analytics — capa de consulta sobre un DataFrame TrackMan.
Funciones puras que devuelven dicts/listas JSON-serializables.
La API Flask (api.py) y el frontend Streamlit consumen estas mismas funciones.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from .engine import compute_pitch_path, pitch_metrics

META_COLS = ["PitchUID","Pitcher","Batter","Date","TaggedPitchType","RelSpeed",
             "SpinRate","SpinAxis","HorzBreak","InducedVertBreak","VertBreak",
             "PlateLocHeight","PlateLocSide","RelHeight","RelSide","Extension",
             "Balls","Strikes","PitchCall","PlayResult","BatterSide","Stadium"]


def ensure_pitch_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza un PitchUID estable (usa el de TrackMan o genera uno por índice)."""
    df = df.copy()
    if "PitchUID" not in df.columns or df["PitchUID"].isna().all():
        df["PitchUID"] = [f"p{i}" for i in range(len(df))]
    else:
        df["PitchUID"] = df["PitchUID"].astype(str)
        dup = df["PitchUID"].duplicated() | df["PitchUID"].isin(["nan","None",""])
        df.loc[dup,"PitchUID"] = [f"p{i}" for i in df.index[dup]]
    return df


def _row_meta(row) -> dict:
    out = {}
    for c in META_COLS:
        if c in row.index:
            v = row[c]
            if isinstance(v, pd.Timestamp):
                v = v.strftime("%Y-%m-%d")
            elif isinstance(v, (np.integer,)): v = int(v)
            elif isinstance(v, (np.floating,)):
                v = None if np.isnan(v) else round(float(v), 3)
            out[c] = v
    return out


def _apply_filters(df, date_from=None, date_to=None, pitch_type=None,
                   count=None, batter_side=None, result=None):
    if date_from is not None and "Date" in df.columns:
        df = df[df["Date"] >= pd.to_datetime(date_from)]
    if date_to is not None and "Date" in df.columns:
        df = df[df["Date"] <= pd.to_datetime(date_to)]
    if pitch_type:
        df = df[df["TaggedPitchType"].astype(str) == str(pitch_type)]
    if count and "Balls" in df.columns and "Strikes" in df.columns:
        b,s = str(count).split("-")
        df = df[(df["Balls"]==int(b)) & (df["Strikes"]==int(s))]
    if batter_side and "BatterSide" in df.columns:
        df = df[df["BatterSide"].astype(str).str.upper().str.startswith(str(batter_side)[0].upper())]
    if result and "PitchCall" in df.columns:
        r = str(result).lower()
        pc = df["PitchCall"].astype(str)
        if r == "strike":
            df = df[pc.isin(["StrikeCalled","StrikeSwinging"])]
        elif r == "ball":
            df = df[pc.isin(["BallCalled","BallinDirt","IntentionalBall"])]
        elif r == "hit":
            df = df[pc.eq("InPlay")]
    return df


def pitch_trajectory_payload(df: pd.DataFrame, pitch_id: str, n_points=50) -> dict:
    """Trayectoria + metadata + métricas de UN pitch. KeyError si no existe."""
    df = ensure_pitch_ids(df)
    sel = df[df["PitchUID"] == str(pitch_id)]
    if sel.empty:
        raise KeyError(f"pitch_id '{pitch_id}' no encontrado")
    row = sel.iloc[0]
    path = compute_pitch_path(row, n_points=n_points)
    return {"pitch_id": str(pitch_id),
            "meta": _row_meta(row),
            "metrics": pitch_metrics(row),
            "n_points": len(path),
            "trajectory": [{"x":p[0],"y":p[1],"z":p[2],"t":p[3]} for p in path]}


def list_pitches(df: pd.DataFrame, pitcher: str, **filters) -> list:
    """Pitches de un pitcher (filtrables) con metadata mínima para el selector."""
    df = ensure_pitch_ids(df)
    sub = df[df["Pitcher"].astype(str) == str(pitcher)]
    sub = _apply_filters(sub, **filters)
    return [_row_meta(r) for _, r in sub.iterrows()]


def movement_profile(df: pd.DataFrame, pitcher: str, **filters) -> dict:
    """Datos para el break chart: un punto por pitch + centroides por tipo."""
    sub = _apply_filters(df[df["Pitcher"].astype(str)==str(pitcher)], **filters)
    vb_col = "InducedVertBreak" if "InducedVertBreak" in sub.columns else "VertBreak"
    need = {"HorzBreak", vb_col, "TaggedPitchType"}
    if not need.issubset(sub.columns):
        return {"pitches": [], "centroids": []}
    sub = sub.dropna(subset=["HorzBreak", vb_col])
    pitches = [{"pitch_type":str(r["TaggedPitchType"]),
                "hb":round(float(r["HorzBreak"]),2),
                "vb":round(float(r[vb_col]),2),
                "velo":(round(float(r["RelSpeed"]),1)
                        if "RelSpeed" in sub.columns and pd.notna(r.get("RelSpeed")) else None)}
               for _, r in sub.iterrows()]
    cents = [{"pitch_type":str(pt),"hb":round(float(g["HorzBreak"].mean()),2),
              "vb":round(float(g[vb_col].mean()),2),"n":int(len(g))}
             for pt, g in sub.groupby("TaggedPitchType")]
    return {"pitcher": pitcher, "vertical_break_col": vb_col,
            "pitches": pitches, "centroids": cents}


def release_consistency(df: pd.DataFrame, pitcher: str, **filters) -> dict:
    """
    Variabilidad del punto de release por fecha (drift mecánico / fatiga).
    std_total = desviación combinada (ft); drift = distancia entre el
    centroide de la primera y la última fecha.
    """
    sub = _apply_filters(df[df["Pitcher"].astype(str)==str(pitcher)], **filters)
    need = {"RelHeight","RelSide"}
    if not need.issubset(sub.columns):
        return {"points": [], "by_date": [], "summary": {}}
    sub = sub.dropna(subset=["RelHeight","RelSide"])
    if sub.empty:
        return {"points": [], "by_date": [], "summary": {}}
    pts = [{"date": (r["Date"].strftime("%Y-%m-%d") if isinstance(r.get("Date"),pd.Timestamp) else None),
            "rel_side": round(float(r["RelSide"]),3),
            "rel_height": round(float(r["RelHeight"]),3),
            "pitch_type": str(r.get("TaggedPitchType","")) }
           for _, r in sub.iterrows()]
    by_date = []
    if "Date" in sub.columns and sub["Date"].notna().any():
        for d, g in sub.groupby(sub["Date"].dt.date):
            by_date.append({"date": str(d), "n": int(len(g)),
                            "mean_side": round(float(g["RelSide"].mean()),3),
                            "mean_height": round(float(g["RelHeight"].mean()),3),
                            "std_side": round(float(g["RelSide"].std(ddof=0)),3),
                            "std_height": round(float(g["RelHeight"].std(ddof=0)),3)})
    drift = None
    if len(by_date) >= 2:
        a, b = by_date[0], by_date[-1]
        drift = round(float(np.hypot(b["mean_side"]-a["mean_side"],
                                     b["mean_height"]-a["mean_height"])), 3)
    summary = {"n": int(len(sub)),
               "std_side": round(float(sub["RelSide"].std(ddof=0)),3),
               "std_height": round(float(sub["RelHeight"].std(ddof=0)),3),
               "std_total": round(float(np.hypot(sub["RelSide"].std(ddof=0),
                                                 sub["RelHeight"].std(ddof=0))),3),
               "drift_first_to_last_ft": drift}
    return {"pitcher": pitcher, "points": pts, "by_date": by_date, "summary": summary}


def velocity_spin_trends(df: pd.DataFrame, pitcher: str, **filters) -> dict:
    """RelSpeed y SpinRate promedio por outing (fecha) y tipo de pitcheo."""
    sub = _apply_filters(df[df["Pitcher"].astype(str)==str(pitcher)], **filters)
    if "Date" not in sub.columns or sub["Date"].isna().all():
        return {"outings": []}
    out = []
    for (d, pt), g in sub.groupby([sub["Date"].dt.date, "TaggedPitchType"]):
        rec = {"date": str(d), "pitch_type": str(pt), "n": int(len(g))}
        for col, key in [("RelSpeed","velo"), ("SpinRate","spin")]:
            if col in g.columns and g[col].notna().any():
                rec[f"avg_{key}"] = round(float(g[col].mean()),1)
                rec[f"max_{key}"] = round(float(g[col].max()),1)
        out.append(rec)
    return {"pitcher": pitcher, "outings": sorted(out, key=lambda r: r["date"])}

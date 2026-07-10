"""
trajectory.api — API Flask del módulo de trayectorias.

Uso:
    from trajectory.api import create_app
    app = create_app(csv_paths=["datos/torneo1.csv", ...])   # o data_frame=df
    app.run(port=5001)

Nota de despliegue: el dashboard principal es Streamlit (Streamlit Cloud no
hospeda Flask). Esta API existe para integraciones externas / migración
futura a cliente-servidor; consume EXACTAMENTE las mismas funciones de
trajectory.analytics que usa el frontend Streamlit.

Endpoints (ver README del paquete para ejemplos completos):
  GET /api/health
  GET /api/pitch/<pitch_id>/trajectory?n_points=50
  GET /api/pitcher/<pitcher_id>/pitches?date_from&date_to&pitch_type&count&batter_side&result
  GET /api/pitcher/<pitcher_id>/movement_profile?date_from&date_to
  GET /api/pitcher/<pitcher_id>/release_consistency?date_from&date_to&pitch_type
  GET /api/pitcher/<pitcher_id>/velocity_spin_trends?pitch_type
"""
from __future__ import annotations
import pandas as pd
from flask import Flask, jsonify, request
from .analytics import (pitch_trajectory_payload, list_pitches, movement_profile,
                        release_consistency, velocity_spin_trends, ensure_pitch_ids)
from .validation import validate_physical, validate_schema


def _load(csv_paths):
    frames = [pd.read_csv(p, low_memory=False) for p in csv_paths]
    df = pd.concat(frames, ignore_index=True)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format="mixed")
    return df


def _filters_from_request():
    a = request.args
    return {"date_from": a.get("date_from"), "date_to": a.get("date_to"),
            "pitch_type": a.get("pitch_type"), "count": a.get("count"),
            "batter_side": a.get("batter_side"), "result": a.get("result")}


def create_app(csv_paths=None, data_frame=None) -> Flask:
    if data_frame is None:
        if not csv_paths:
            raise ValueError("Pasa csv_paths=[...] o data_frame=DataFrame")
        data_frame = _load(csv_paths)
    df, phys_report = validate_physical(data_frame)
    df = ensure_pitch_ids(df)
    schema = validate_schema(df)

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "n_pitches": int(len(df)),
                        "schema": schema, "physical_validation": phys_report})

    @app.get("/api/pitch/<pitch_id>/trajectory")
    def pitch_trajectory(pitch_id):
        n = request.args.get("n_points", default=50, type=int)
        try:
            return jsonify(pitch_trajectory_payload(df, pitch_id, n_points=max(2, min(n, 500))))
        except KeyError as e:
            return jsonify({"error": str(e)}), 404
        except ValueError as e:
            return jsonify({"error": f"datos insuficientes: {e}"}), 422

    @app.get("/api/pitcher/<pitcher_id>/pitches")
    def pitcher_pitches(pitcher_id):
        rows = list_pitches(df, pitcher_id, **_filters_from_request())
        return jsonify({"pitcher": pitcher_id, "n": len(rows), "pitches": rows})

    @app.get("/api/pitcher/<pitcher_id>/movement_profile")
    def pitcher_movement(pitcher_id):
        return jsonify(movement_profile(df, pitcher_id, **_filters_from_request()))

    @app.get("/api/pitcher/<pitcher_id>/release_consistency")
    def pitcher_release(pitcher_id):
        return jsonify(release_consistency(df, pitcher_id, **_filters_from_request()))

    @app.get("/api/pitcher/<pitcher_id>/velocity_spin_trends")
    def pitcher_trends(pitcher_id):
        return jsonify(velocity_spin_trends(df, pitcher_id, **_filters_from_request()))

    return app


if __name__ == "__main__":  # pragma: no cover
    import sys
    create_app(csv_paths=sys.argv[1:]).run(port=5001, debug=False)

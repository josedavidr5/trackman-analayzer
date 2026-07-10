"""
Tests del motor de trayectoria — verifica que la física sea consistente
con los datos que reporta TrackMan.
Correr:  pytest trajectory/tests/ -v
"""
import math
import pytest
from trajectory.engine import (compute_pitch_path, pitch_metrics,
                               initial_conditions, PLATE_Y, G)
from trajectory.validation import validate_physical, validate_schema
import pandas as pd
import numpy as np

FASTBALL = {  # recta típica de 95 mph con ride
    "RelSpeed": 95.0, "Extension": 6.5, "RelHeight": 5.9, "RelSide": -1.8,
    "HorzBreak": 8.0, "InducedVertBreak": 16.0,
    "PlateLocSide": 0.2, "PlateLocHeight": 2.8, "SpinRate": 2400.0,
}
SLIDER = {
    "RelSpeed": 84.0, "Extension": 6.3, "RelHeight": 5.7, "RelSide": -1.9,
    "HorzBreak": -6.0, "InducedVertBreak": 1.0,
    "PlateLocSide": -0.5, "PlateLocHeight": 1.9, "SpinRate": 2600.0,
}


def test_path_endpoints_match_trackman():
    """El modelo debe reproducir EXACTAMENTE release y ubicación en el plato."""
    for pitch in (FASTBALL, SLIDER):
        path = compute_pitch_path(pitch, n_points=50)
        x0, y0, z0, t0 = path[0]
        xf, yf, zf, tf = path[-1]
        assert t0 == 0.0
        assert y0 == pytest.approx(60.5 - pitch["Extension"], abs=1e-3)
        assert z0 == pytest.approx(pitch["RelHeight"], abs=1e-3)
        assert x0 == pytest.approx(pitch["RelSide"], abs=1e-3)
        assert yf == pytest.approx(PLATE_Y, abs=1e-3)
        assert xf == pytest.approx(pitch["PlateLocSide"], abs=1e-2)
        assert zf == pytest.approx(pitch["PlateLocHeight"], abs=1e-2)


def test_y_monotonic_and_n_points():
    path = compute_pitch_path(FASTBALL, n_points=80)
    assert len(path) == 80
    ys = [p[1] for p in path]
    assert all(a > b for a, b in zip(ys, ys[1:])), "y debe decrecer hacia el plato"


def test_flight_time_reasonable():
    """95 mph ≈ 0.40–0.46 s; 84 mph ≈ 0.45–0.52 s (rangos de la literatura)."""
    m_fb = pitch_metrics(FASTBALL)
    m_sl = pitch_metrics(SLIDER)
    assert 0.38 < m_fb["flight_time"] < 0.48
    assert 0.44 < m_sl["flight_time"] < 0.56
    assert m_sl["flight_time"] > m_fb["flight_time"]


def test_vaa_typical_range():
    """VAA de una recta alta: entre -3 y -7 grados aprox (siempre cayendo)."""
    m = pitch_metrics(FASTBALL)
    assert -8.0 < m["vaa_deg"] < -2.0
    m2 = pitch_metrics(SLIDER)
    assert m2["vaa_deg"] < m["vaa_deg"], "el slider debe llegar más empinado"


def test_no_break_pitch_is_pure_gravity():
    """Sin break, la aceleración vertical debe ser exactamente -g y ax=0."""
    pitch = dict(FASTBALL, HorzBreak=0.0, InducedVertBreak=0.0)
    ic = initial_conditions(pitch)
    assert ic["ax"] == pytest.approx(0.0, abs=1e-9)
    assert ic["az"] == pytest.approx(-G, abs=1e-9)


def test_kinematic_mode_priority():
    """Con paquete 9P, el motor debe integrarlo directamente."""
    pitch = {"x0":-1.5,"y0":54.0,"z0":5.8,"vx0":3.0,"vy0":-138.0,"vz0":-4.0,
             "ax0":6.0,"ay0":25.0,"az0":-20.0}
    ic = initial_conditions(pitch)
    assert ic["source"] == "kinematic"
    path = compute_pitch_path(pitch, n_points=50)
    assert path[-1][1] == pytest.approx(PLATE_Y, abs=1e-3)
    # posición manual a t medio
    t = path[25][3]
    assert path[25][2] == pytest.approx(5.8 + (-4.0)*t + 0.5*(-20.0)*t*t, abs=1e-3)


def test_plate_speed_less_than_release():
    m = pitch_metrics(FASTBALL)
    assert m["plate_speed_mph"] < FASTBALL["RelSpeed"]
    assert m["plate_speed_mph"] > FASTBALL["RelSpeed"]*0.85


def test_spin_efficiency_bounds():
    m = pitch_metrics(FASTBALL)
    assert m["spin_efficiency"] is None or 0.0 <= m["spin_efficiency"] <= 1.0
    no_spin = dict(FASTBALL); no_spin.pop("SpinRate")
    assert pitch_metrics(no_spin)["spin_efficiency"] is None


def test_missing_data_raises():
    with pytest.raises(ValueError):
        compute_pitch_path({"RelSpeed": 90.0})  # sin PlateLoc


def test_validate_physical_flags_capture_errors():
    df = pd.DataFrame({"RelSpeed":[92.0, 250.0, 30.0, np.nan],
                       "SpinRate":[2200.0, 5000.0, 1800.0, 2100.0]})
    clean, report = validate_physical(df)
    assert report == {"RelSpeed": 2, "SpinRate": 1}
    assert clean["RelSpeed"].notna().sum() == 1
    assert clean["SpinRate"].notna().sum() == 3


def test_validate_schema():
    df = pd.DataFrame(columns=["Pitcher","Batter","Date","TaggedPitchType",
                               "RelSpeed","RelHeight","RelSide","Extension",
                               "HorzBreak","InducedVertBreak","PlateLocHeight",
                               "PlateLocSide","SpinRate","SpinAxis","Balls","Strikes"])
    rep = validate_schema(df)
    assert rep["missing_required"] == []
    assert rep["trajectory_ready"] is True
    assert rep["has_9p_kinematics"] is False


def test_name_dedup_fuzzy():
    """Regresión v4.7: variantes del mismo jugador se unifican; distintos no."""
    import importlib.util, sys, os
    spec=importlib.util.spec_from_file_location(
        "tmapp", os.path.join(os.path.dirname(__file__),"..","..","trackman_app.py"))
    tm=importlib.util.module_from_spec(spec); spec.loader.exec_module(tm)
    sucios=["Jose Perez","José Pérez","Jose Peres","J. Perez","Perez, Jose",
            "JOSE PEREZ ","Luis Perez","Deybi Jimenez","Deibi Jimenez",
            "Ana Lopez","Anna Lopez","Abel Perez"]
    norm=[tm.normalize_name(s) for s in sucios]
    m=tm.find_clusters(norm)
    # mismo jugador → mismo canónico
    assert m["Jose Peres"]==m["Jose Perez"]=="Jose Perez"
    assert m["J Perez"]=="Jose Perez"
    assert m["Deibi Jimenez"]==m["Deybi Jimenez"]
    assert m["Anna Lopez"]==m["Ana Lopez"]
    # jugadores DISTINTOS no se mezclan
    assert m["Luis Perez"]=="Luis Perez"
    assert m["Abel Perez"]=="Abel Perez"

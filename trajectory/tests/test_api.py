"""Tests de la API Flask con test client (sin red)."""
import numpy as np
import pandas as pd
import pytest
from trajectory.api import create_app


@pytest.fixture
def client():
    rng = np.random.default_rng(5)
    n = 60
    df = pd.DataFrame({
        "PitchUID": [f"u{i}" for i in range(n)],
        "Pitcher": ["Juan Perez"]*40 + ["Carlos Diaz"]*20,
        "Batter": rng.choice(["Luis Gomez","Ana Lopez"], n),
        "BatterSide": rng.choice(["Right","Left"], n),
        "TaggedPitchType": rng.choice(["4-Seam","Slider"], n),
        "PitchCall": rng.choice(["StrikeCalled","BallCalled","InPlay"], n),
        "RelSpeed": rng.normal(91, 3, n), "SpinRate": rng.normal(2300, 150, n),
        "SpinAxis": rng.uniform(0, 360, n),
        "RelHeight": rng.normal(5.8, 0.1, n), "RelSide": rng.normal(-1.7, 0.1, n),
        "Extension": rng.normal(6.3, 0.2, n),
        "HorzBreak": rng.normal(4, 6, n), "InducedVertBreak": rng.normal(10, 6, n),
        "PlateLocSide": rng.normal(0, 0.7, n), "PlateLocHeight": rng.normal(2.5, 0.6, n),
        "Balls": rng.integers(0, 4, n), "Strikes": rng.integers(0, 3, n),
        "Date": pd.to_datetime(rng.choice(pd.date_range("2026-06-01","2026-06-20"), n)),
    })
    return create_app(data_frame=df).test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok" and body["n_pitches"] == 60
    assert body["schema"]["trajectory_ready"] is True


def test_trajectory_endpoint(client):
    r = client.get("/api/pitch/u3/trajectory?n_points=40")
    assert r.status_code == 200
    body = r.get_json()
    assert body["n_points"] == 40
    assert {"x","y","z","t"} <= set(body["trajectory"][0])
    assert body["metrics"]["flight_time"] > 0.3
    assert body["meta"]["Pitcher"] == "Juan Perez"


def test_trajectory_404(client):
    assert client.get("/api/pitch/nope/trajectory").status_code == 404


def test_pitches_filterable(client):
    r = client.get("/api/pitcher/Juan Perez/pitches?pitch_type=Slider")
    body = r.get_json()
    assert body["n"] >= 1
    assert all(p["TaggedPitchType"] == "Slider" for p in body["pitches"])
    r2 = client.get("/api/pitcher/Juan Perez/pitches?date_from=2026-06-10&date_to=2026-06-12")
    assert all("2026-06-10" <= p["Date"] <= "2026-06-12" for p in r2.get_json()["pitches"])


def test_movement_profile(client):
    body = client.get("/api/pitcher/Juan Perez/movement_profile").get_json()
    assert body["pitches"] and body["centroids"]
    assert {"pitch_type","hb","vb","n"} <= set(body["centroids"][0])


def test_release_consistency(client):
    body = client.get("/api/pitcher/Juan Perez/release_consistency").get_json()
    assert body["summary"]["n"] == 40
    assert body["summary"]["std_total"] < 0.5
    assert len(body["by_date"]) >= 2


def test_velocity_spin_trends(client):
    body = client.get("/api/pitcher/Carlos Diaz/velocity_spin_trends").get_json()
    assert body["outings"]
    assert {"date","pitch_type","n","avg_velo","avg_spin"} <= set(body["outings"][0])

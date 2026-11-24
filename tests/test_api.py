"""Smoke tests for the HiGHS solver API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["highs_version"]


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "higs-solver-api"


def test_solve_lp():
    # min x + y  s.t.  x + 2y >= 4, 4x + 2y >= 12, x,y >= 0
    # optimum: x = 8/3, y = 2/3, obj = 10/3
    r = client.post(
        "/solve",
        json={
            "objective": {"c": [1, 1], "sense": "minimize"},
            "constraints": [
                {"a": [1, 2], "sense": "ge", "rhs": 4},
                {"a": [4, 2], "sense": "ge", "rhs": 12},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "optimal"
    assert abs(body["objective_value"] - 10 / 3) < 1e-6
    assert abs(body["solution"][0] - 8 / 3) < 1e-6
    assert abs(body["solution"][1] - 2 / 3) < 1e-6


def test_solve_mip():
    # max 3x + 2y  s.t.  x + y <= 4, x <= 2 (integer), y >= 0
    r = client.post(
        "/solve",
        json={
            "objective": {"c": [3, 2], "sense": "maximize"},
            "constraints": [
                {"a": [1, 1], "sense": "le", "rhs": 4},
            ],
            "bounds": [
                {"lb": 0, "ub": 2},
                {"lb": 0, "ub": None},
            ],
            "integrality": ["integer", "continuous"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "optimal"
    assert abs(body["objective_value"] - 10.0) < 1e-6


def test_solve_validation_error():
    r = client.post(
        "/solve",
        json={
            "objective": {"c": [1, 1]},
            "constraints": [{"a": [1], "sense": "ge", "rhs": 1}],
        },
    )
    assert r.status_code == 422

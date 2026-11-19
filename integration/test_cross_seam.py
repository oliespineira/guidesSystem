"""Cross-seam tests against the real system started with `docker compose up`.

No fakes: actas really calls kraal over HTTP. Run from the repo root with the stack up:
    python -m pytest -q integration
"""

import subprocess
import time

import httpx
import pytest

KRAAL = "http://localhost:8001"
ACTAS = "http://localhost:8002"


@pytest.fixture(scope="module", autouse=True)
def system_is_up():
    """Wait until both services answer /health (first start includes SQL Server and migrations)."""
    deadline = time.monotonic() + 180
    for url in (KRAAL, ACTAS):
        while True:
            try:
                if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                pytest.fail(f"{url} did not become healthy in time")
            time.sleep(2)


def test_actas_builds_notice_topics_from_real_kraal_data():
    label = f"it-{time.time_ns() % 10**12}"  # unique per run, and short enough for NVARCHAR(20)
    rid = httpx.post(f"{KRAAL}/api/kraal/rondas", json={"year_label": label, "start_date": "2026-09-01"}).json()["id"]
    rama = httpx.post(f"{KRAAL}/api/kraal/rondas/{rid}/ramas", json={"name": "Guías"}).json()["id"]
    vid = httpx.post(f"{KRAAL}/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    httpx.post(f"{KRAAL}/api/kraal/ramas/{rama}/members", json={"volunteer_id": vid, "availability_pct": 100})
    httpx.post(f"{KRAAL}/api/kraal/rondas/{rid}/roles", json={"volunteer_id": vid, "role_name": "Tesorera"})

    topics = httpx.get(f"{ACTAS}/api/avisos/topics", params={"ronda_id": rid, "volunteer_id": vid}).json()

    assert topics == [f"ronda.{rid}.all", f"ronda.{rid}.rama.guias", f"ronda.{rid}.role.tesorera"]


def test_kraal_down_cross_seam_flow_fails_clearly_and_actas_keeps_serving():
    subprocess.run(["docker", "compose", "stop", "kraal"], check=True)
    try:
        assert httpx.get(f"{ACTAS}/health").status_code == 200
        topics = httpx.get(f"{ACTAS}/api/avisos/topics", params={"ronda_id": 1, "volunteer_id": 1}, timeout=10)
        assert topics.status_code == 503
        assert topics.json()["detail"] == "El servicio Kraal no está disponible; inténtalo de nuevo"
        assert httpx.get(f"{ACTAS}/api/actas/meetings", params={"ronda_id": 1}).status_code == 200
    finally:
        subprocess.run(["docker", "compose", "start", "kraal"], check=True)

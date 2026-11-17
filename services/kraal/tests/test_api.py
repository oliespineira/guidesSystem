def _ronda(client, label="2026"):
    return client.post("/api/kraal/rondas", json={"year_label": label, "start_date": "2026-09-01"})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "db": "ok", "version": "local"}


def test_health_is_503_when_the_database_fails(client, monkeypatch):
    import app.main

    def broken(*args, **kwargs):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(app.main, "get_connection", broken)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["db"] == "error"


def test_duplicate_ronda_returns_409(client):
    assert _ronda(client).status_code == 201
    assert _ronda(client).status_code == 409


def test_unknown_ronda_roster_returns_404(client):
    assert client.get("/api/kraal/rondas/999/roster").status_code == 404


def test_bad_date_is_rejected_by_pydantic(client):
    r = client.post("/api/kraal/rondas", json={"year_label": "x", "start_date": "not-a-date"})
    assert r.status_code == 422


def test_list_volunteers_over_http(client):
    vid = client.post("/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    assert client.get("/api/kraal/volunteers").json() == [{"id": vid, "name": "Ana"}]


def test_list_roles_over_http(client):
    rid = _ronda(client).json()["id"]
    ana = client.post("/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    client.post(f"/api/kraal/rondas/{rid}/roles", json={"volunteer_id": ana, "role_name": "Tesorera"})
    assert client.get(f"/api/kraal/rondas/{rid}/roles").json() == [
        {"role_name": "Tesorera", "volunteer_id": ana, "volunteer_name": "Ana"}
    ]


def test_seam_endpoints_answer_what_actas_needs(client):
    rid = _ronda(client).json()["id"]
    rama = client.post(f"/api/kraal/rondas/{rid}/ramas", json={"name": "Guías"}).json()["id"]
    ana = client.post("/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    client.post(f"/api/kraal/ramas/{rama}/members", json={"volunteer_id": ana})
    client.post(f"/api/kraal/rondas/{rid}/roles", json={"volunteer_id": ana, "role_name": "Tesorera"})

    assert client.get(f"/api/kraal/rondas/{rid}").json()["id"] == rid
    assert client.get(f"/api/kraal/rondas/{rid}/members").json() == [ana]
    assert client.get(f"/api/kraal/rondas/{rid}/volunteers/{ana}/membership").json() == {
        "volunteer_id": ana,
        "name": "Ana",
        "rama": "Guías",
        "roles": ["Tesorera"],
    }


def test_seam_endpoints_return_404_for_unknown_ids(client):
    rid = _ronda(client).json()["id"]
    assert client.get("/api/kraal/rondas/999").status_code == 404
    assert client.get(f"/api/kraal/rondas/{rid}/volunteers/999/membership").status_code == 404


def test_too_long_label_is_rejected_by_pydantic_not_the_database(client):
    r = client.post("/api/kraal/rondas", json={"year_label": "x" * 21, "start_date": "2026-09-01"})
    assert r.status_code == 422

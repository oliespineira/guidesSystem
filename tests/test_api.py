def _ronda(client, label="2026"):
    return client.post("/api/kraal/rondas", json={"year_label": label, "start_date": "2026-09-01"})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_duplicate_ronda_returns_409(client):
    assert _ronda(client).status_code == 201
    assert _ronda(client).status_code == 409


def test_unknown_ronda_roster_returns_404(client):
    assert client.get("/api/kraal/rondas/999/roster").status_code == 404


def test_bad_date_is_rejected_by_pydantic(client):
    r = client.post("/api/kraal/rondas", json={"year_label": "x", "start_date": "not-a-date"})
    assert r.status_code == 422


def test_meeting_flow_end_to_end(client):
    rid = _ronda(client).json()["id"]
    mid = client.post("/api/actas/meetings",
                      json={"ronda_id": rid, "date": "2026-10-01", "title": "Kickoff"}).json()["id"]
    item = client.post(f"/api/actas/meetings/{mid}/agenda",
                       json={"section_title": "Budget"}).json()["id"]
    client.post(f"/api/actas/agenda/{item}/decisions", json={"description": "Approve budget"})
    summary = client.get(f"/api/actas/meetings/{mid}").json()
    assert summary["agenda"][0]["decisions"][0]["description"] == "Approve budget"

def _budget(client, ronda_id, cents=10000):
    return client.post("/api/actas/budgets",
                       json={"ronda_id": ronda_id, "category": "Material", "allocated_cents": cents}).json()["id"]


def test_over_budget_request_is_rejected_and_cannot_be_paid(client, monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    bid = _budget(client, _ronda(client).json()["id"])
    r = client.post(f"/api/actas/budgets/{bid}/requests",
                    json={"rama": "Guias", "item": "Tiendas", "amount_cents": 20000})
    assert r.status_code == 201 and r.json()["status"] == "rejected"
    pay = client.post(f"/api/actas/requests/{r.json()['id']}/pay", json={"payment_ref": "TRF-1"})
    assert pay.status_code == 409


def test_request_approve_pay_and_history_over_http(client, monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    bid = _budget(client, _ronda(client).json()["id"])
    rid = client.post(f"/api/actas/budgets/{bid}/requests",
                      json={"rama": "Guias", "item": "Albergue", "amount_cents": 3000}).json()["id"]
    assert client.post(f"/api/actas/requests/{rid}/approve", json={"actor": "Tesorera"}).status_code == 200
    assert client.post(f"/api/actas/requests/{rid}/pay", json={"payment_ref": "TRF-42"}).status_code == 200
    actions = [h["action"] for h in client.get(f"/api/actas/requests/{rid}/history").json()]
    assert actions == ["submitted", "approved", "paid"]
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


def test_post_notice_to_a_rama_and_reject_bad_audience(client):
    rid = _ronda(client).json()["id"]
    r = client.post("/api/avisos", json={"ronda_id": rid, "audience": "rama", "target": "Guías",
                                         "title": "Salida el sábado"})
    assert r.status_code == 201 and r.json()["topic"] == f"ronda.{rid}.rama.guias"
    bad = client.post("/api/avisos", json={"ronda_id": rid, "audience": "everyone", "title": "x"})
    assert bad.status_code == 400


def test_volunteer_topics_over_http(client):
    rid = _ronda(client).json()["id"]
    vid = client.post("/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    assert client.get("/api/kraal/volunteers").json() == [{"id": vid, "name": "Ana"}]
    assert client.get(f"/api/avisos/topics?ronda_id={rid}&volunteer_id={vid}").json() == [f"ronda.{rid}.all"]


def test_vote_flow_over_http(client):
    rid = _ronda(client).json()["id"]
    rama = client.post(f"/api/kraal/rondas/{rid}/ramas", json={"name": "Guías"}).json()["id"]
    ana = client.post("/api/kraal/volunteers", json={"name": "Ana"}).json()["id"]
    client.post(f"/api/kraal/ramas/{rama}/members", json={"volunteer_id": ana})
    mid = client.post("/api/actas/meetings", json={"ronda_id": rid, "date": "2026-10-01", "title": "K"}).json()["id"]
    item = client.post(f"/api/actas/meetings/{mid}/agenda", json={"section_title": "Material"}).json()["id"]
    dec = client.post(f"/api/actas/agenda/{item}/decisions", json={"description": "Buy tents"}).json()["id"]

    assert client.post(f"/api/actas/decisions/{dec}/vote", json={"closes_at": "2099-01-01T20:00"}).status_code == 201
    assert client.post(f"/api/actas/decisions/{dec}/votes", json={"volunteer_id": ana, "choice": "yes"}).status_code == 201
    assert client.post(f"/api/actas/decisions/{dec}/votes", json={"volunteer_id": ana, "choice": "no"}).status_code == 409
    assert client.get(f"/api/actas/decisions/{dec}/votes").json()["yes"] == 1
    assert client.post(f"/api/actas/decisions/{dec}/vote/close").status_code == 409    # still open

    def test_booking_flow_over_http(client):
        rid = _ronda(client).json()["id"]
        ev = client.post("/api/actas/calendar", json={"ronda_id": rid, "start_date": "2099-03-20",
                                                    "activity_type": "Camp"}).json()["id"]
        assert client.post(f"/api/actas/calendar/{ev}/booking", json={"book_by": "2099-01-15"}).status_code == 201
        assert client.post(f"/api/actas/calendar/{ev}/booking", json={}).status_code == 409
        assert client.post(f"/api/actas/calendar/{ev}/booking/done", json={"venue": "Cercedilla"}).status_code == 200
        assert client.get(f"/api/actas/bookings?ronda_id={rid}").json()[0]["status"] == "booked"
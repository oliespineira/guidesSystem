from app.db import get_connection


def _ronda(kraal, label="2026"):
    return kraal.create_ronda(None, label, "2026-09-01")


def _budget(client, ronda_id, cents=10000):
    return client.post(
        "/api/actas/budgets", json={"ronda_id": ronda_id, "category": "Material", "allocated_cents": cents}
    ).json()["id"]


def _treasurer(kraal, ronda_id, name="Tesorera"):
    tid = kraal.add_volunteer(None, name)
    kraal.assign_role(None, ronda_id, tid, "Tesorera")
    return tid


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


def test_meeting_flow_end_to_end(client, kraal):
    rid = _ronda(kraal)
    mid = client.post("/api/actas/meetings", json={"ronda_id": rid, "date": "2026-10-01", "title": "Kickoff"}).json()[
        "id"
    ]
    item = client.post(f"/api/actas/meetings/{mid}/agenda", json={"section_title": "Budget"}).json()["id"]
    client.post(f"/api/actas/agenda/{item}/decisions", json={"description": "Approve budget"})
    summary = client.get(f"/api/actas/meetings/{mid}").json()
    assert summary["agenda"][0]["decisions"][0]["description"] == "Approve budget"


def test_over_budget_request_is_rejected_and_cannot_be_paid(client, kraal, monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    rid = _ronda(kraal)
    bid, tid = _budget(client, rid), _treasurer(kraal, rid)
    r = client.post(
        f"/api/actas/budgets/{bid}/requests", json={"rama": "Guias", "item": "Tiendas", "amount_cents": 20000}
    )
    assert r.status_code == 201 and r.json()["status"] == "rejected"
    pay = client.post(f"/api/actas/requests/{r.json()['id']}/pay", json={"payment_ref": "TRF-1", "volunteer_id": tid})
    assert pay.status_code == 409


def test_request_approve_pay_and_history_over_http(client, kraal, monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    ronda_id = _ronda(kraal)
    bid, tid = _budget(client, ronda_id), _treasurer(kraal, ronda_id, name="Marta")
    ana = kraal.add_volunteer(None, "Ana")
    assert client.get(f"/api/actas/treasury?ronda_id={ronda_id}").json() == {"role": "Tesorera", "volunteer_ids": [tid]}
    rid = client.post(
        f"/api/actas/budgets/{bid}/requests", json={"rama": "Guias", "item": "Albergue", "amount_cents": 3000}
    ).json()["id"]
    assert client.post(f"/api/actas/requests/{rid}/approve", json={"volunteer_id": ana}).status_code == 403
    assert client.post(f"/api/actas/requests/{rid}/approve", json={"volunteer_id": tid}).status_code == 200
    assert (
        client.post(f"/api/actas/requests/{rid}/pay", json={"payment_ref": "TRF-42", "volunteer_id": tid}).status_code
        == 200
    )
    history = client.get(f"/api/actas/requests/{rid}/history").json()
    assert [(h["action"], h["actor"]) for h in history] == [
        ("submitted", "Guias"),
        ("approved", "Marta"),
        ("paid", "Marta"),
    ]


def test_post_notice_to_a_rama_and_reject_bad_audience(client, kraal):
    rid = _ronda(kraal)
    r = client.post(
        "/api/avisos", json={"ronda_id": rid, "audience": "rama", "target": "Guías", "title": "Salida el sábado"}
    )
    assert r.status_code == 201 and r.json()["topic"] == f"ronda.{rid}.rama.guias"
    bad = client.post("/api/avisos", json={"ronda_id": rid, "audience": "everyone", "title": "x"})
    assert bad.status_code == 400


def test_volunteer_topics_over_http(client, kraal):
    rid = _ronda(kraal)
    vid = kraal.add_volunteer(None, "Ana")
    assert client.get(f"/api/avisos/topics?ronda_id={rid}&volunteer_id={vid}").json() == [f"ronda.{rid}.all"]


def test_vote_flow_over_http(client, kraal):
    rid = _ronda(kraal)
    rama = kraal.create_rama(None, rid, "Guías")
    ana = kraal.add_volunteer(None, "Ana")
    kraal.assign_to_rama(None, rama, ana)
    mid = client.post("/api/actas/meetings", json={"ronda_id": rid, "date": "2026-10-01", "title": "K"}).json()["id"]
    item = client.post(f"/api/actas/meetings/{mid}/agenda", json={"section_title": "Material"}).json()["id"]
    dec = client.post(f"/api/actas/agenda/{item}/decisions", json={"description": "Buy tents"}).json()["id"]

    assert client.post(f"/api/actas/decisions/{dec}/vote", json={"closes_at": "2099-01-01T20:00"}).status_code == 201
    assert (
        client.post(f"/api/actas/decisions/{dec}/votes", json={"volunteer_id": ana, "choice": "yes"}).status_code == 201
    )
    assert (
        client.post(f"/api/actas/decisions/{dec}/votes", json={"volunteer_id": ana, "choice": "no"}).status_code == 409
    )
    assert client.get(f"/api/actas/decisions/{dec}/votes").json()["yes"] == 1
    assert client.post(f"/api/actas/decisions/{dec}/vote/close").status_code == 409  # still open


def test_booking_flow_over_http(client, kraal):
    rid = _ronda(kraal)
    ev = client.post(
        "/api/actas/calendar", json={"ronda_id": rid, "start_date": "2099-03-20", "activity_type": "Camp"}
    ).json()["id"]
    assert client.post(f"/api/actas/calendar/{ev}/booking", json={"book_by": "2099-01-15"}).status_code == 201
    assert client.post(f"/api/actas/calendar/{ev}/booking", json={}).status_code == 409
    assert client.post(f"/api/actas/calendar/{ev}/booking/done", json={"venue": "Cercedilla"}).status_code == 200
    assert client.get(f"/api/actas/bookings?ronda_id={rid}").json()[0]["status"] == "booked"


def test_list_requests_over_http(client, kraal):
    rid = _ronda(kraal)
    bid = _budget(client, rid)
    client.post(f"/api/actas/budgets/{bid}/requests", json={"rama": "Guias", "item": "Tiendas", "amount_cents": 3000})
    [req] = client.get(f"/api/actas/requests?ronda_id={rid}").json()
    assert (req["category"], req["rama"], req["item"]) == ("Material", "Guias", "Tiendas")
    assert client.get("/api/actas/requests?ronda_id=999").status_code == 404


def test_request_routes_send_notices(client, kraal, monkeypatch):
    monkeypatch.delenv("APPROVAL_POLICY", raising=False)
    rid = _ronda(kraal)
    bid, tid = _budget(client, rid), _treasurer(kraal, rid)
    req = client.post(
        f"/api/actas/budgets/{bid}/requests", json={"rama": "Guias", "item": "Tiendas", "amount_cents": 3000}
    ).json()["id"]
    client.post(f"/api/actas/requests/{req}/approve", json={"volunteer_id": tid})
    conn = get_connection()
    topics = [r["topic"] for r in conn.execute("SELECT topic FROM notices ORDER BY id")]
    conn.close()
    assert topics == [f"ronda.{rid}.role.tesorera", f"ronda.{rid}.rama.guias"]


def test_kraal_down_writes_fail_with_503_but_reads_still_work(client, kraal):
    rid = _ronda(kraal)
    kraal.down = True
    r = client.post("/api/actas/meetings", json={"ronda_id": rid, "date": "2026-10-01", "title": "K"})
    assert r.status_code == 503
    assert r.json() == {"detail": "El servicio Kraal no está disponible; inténtalo de nuevo"}
    assert client.get(f"/api/actas/meetings?ronda_id={rid}").status_code == 200
    assert client.get(f"/api/avisos/topics?ronda_id={rid}&volunteer_id=1").status_code == 503

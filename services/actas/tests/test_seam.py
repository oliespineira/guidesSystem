import httpx
import pytest

from app.actas import seam
from app.actas.seam import _kraal_get as real_kraal_get  # imported before the FakeKraal fixture replaces it
from app.errors import NotFoundError, ServiceUnavailableError


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_success_returns_the_json_and_uses_the_configured_url_and_timeout(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(200, [1, 2])

    monkeypatch.setenv("KRAAL_URL", "http://kraal-test:9000")
    monkeypatch.setenv("KRAAL_TIMEOUT_S", "1.5")
    monkeypatch.setattr(seam.httpx, "get", fake_get)
    assert real_kraal_get("/api/kraal/rondas/1/members") == [1, 2]
    assert calls == [("http://kraal-test:9000/api/kraal/rondas/1/members", 1.5)]


def test_defaults_to_the_compose_service_name(monkeypatch):
    calls = []
    monkeypatch.delenv("KRAAL_URL", raising=False)
    monkeypatch.delenv("KRAAL_TIMEOUT_S", raising=False)
    monkeypatch.setattr(seam.httpx, "get", lambda url, timeout: calls.append((url, timeout)) or FakeResponse(200, {}))
    real_kraal_get("/api/kraal/rondas/1")
    assert calls == [("http://kraal:8000/api/kraal/rondas/1", 2.0)]


def test_a_404_from_kraal_stays_a_not_found(monkeypatch):
    monkeypatch.setattr(seam.httpx, "get", lambda url, timeout: FakeResponse(404, {"detail": "rondas id 9 not found"}))
    with pytest.raises(NotFoundError, match="rondas id 9 not found"):
        real_kraal_get("/api/kraal/rondas/9")


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("too slow")])
def test_no_answer_becomes_a_503(monkeypatch, error):
    def fake_get(url, timeout):
        raise error

    monkeypatch.setattr(seam.httpx, "get", fake_get)
    with pytest.raises(ServiceUnavailableError):
        real_kraal_get("/api/kraal/rondas/1")


def test_a_kraal_crash_becomes_a_503(monkeypatch):
    monkeypatch.setattr(seam.httpx, "get", lambda url, timeout: FakeResponse(500, {"detail": "boom"}))
    with pytest.raises(ServiceUnavailableError):
        real_kraal_get("/api/kraal/rondas/1")
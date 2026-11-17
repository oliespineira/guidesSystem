import json
from pathlib import Path

from app.main import app


def test_committed_openapi_matches_the_code():
    committed = json.loads((Path(__file__).parent.parent / "openapi.json").read_text(encoding="utf-8"))
    assert committed == app.openapi(), "Routes changed: regenerate openapi.json (see README)"

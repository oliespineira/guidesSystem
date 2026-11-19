from app.db import _connect_args


def test_encryption_comes_from_the_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p%40ss@db.example.net:1433/kraal?encrypt=require")
    args = _connect_args()
    assert args["encryption"] == "require"
    assert args["password"] == "p@ss"  # %40 in the URL is an encoded @
    assert args["database"] == "kraal"


def test_no_encryption_setting_means_none_is_passed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@localhost:1433/kraal_test")
    assert "encryption" not in _connect_args()

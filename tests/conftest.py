import pytest

from backend import config, db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "test.db")
    db.init_db()
    yield

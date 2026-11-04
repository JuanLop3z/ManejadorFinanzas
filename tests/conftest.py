import pytest
from database.connection import create_database


@pytest.fixture(autouse=True)
def isolate_private_config(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.LOCAL_CONFIG_PATH", tmp_path / "local_config.json")


@pytest.fixture
def engine(tmp_path):
    database = create_database(tmp_path / "test.db")
    yield database
    database.dispose()

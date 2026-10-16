import pytest

from hub_mcp.db import Db
from hub_mcp.settings import load_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture
def richrich_db(settings):
    if not settings.richrich_database_url:
        pytest.skip("RICHRICH_DATABASE_URL not set")
    db = Db(settings.richrich_database_url, "RichRich", "RICHRICH_DATABASE_URL")
    yield db
    db.close()


@pytest.fixture
def apt_db(settings):
    if not settings.apt_database_url:
        pytest.skip("APT_DATABASE_URL not set")
    db = Db(settings.apt_database_url, "apt-leader", "APT_DATABASE_URL")
    yield db
    db.close()

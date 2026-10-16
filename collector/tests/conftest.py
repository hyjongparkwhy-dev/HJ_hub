import pytest

from hub_collect.settings import load_database_url
from hub_collect.store import connect


@pytest.fixture
def conn():
    url = load_database_url()
    if not url:
        pytest.skip("HUB_DATABASE_URL not set")
    with connect(url) as c:
        yield c

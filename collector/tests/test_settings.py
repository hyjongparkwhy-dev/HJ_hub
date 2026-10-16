from hub_collect.settings import load_database_url


def test_env_wins_over_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("HUB_DATABASE_URL=from-file\n", encoding="utf-8")
    assert load_database_url({"HUB_DATABASE_URL": "from-env"}, f) == "from-env"
    assert load_database_url({}, f) == "from-file"


def test_missing_is_none(tmp_path):
    assert load_database_url({}, tmp_path / "none.env") is None
    assert load_database_url({"HUB_DATABASE_URL": "  "}, tmp_path / "none.env") is None

import pytest

from hub_mcp.settings import load_settings, read_env_file


def test_reads_env_file_ignoring_comments_and_quotes(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# note\nAPT_HOME_KEY="seq:1-2"\n\nAPT_HOME_BAND=74\nbroken line\n', encoding="utf-8")
    assert read_env_file(f) == {"APT_HOME_KEY": "seq:1-2", "APT_HOME_BAND": "74"}


def test_missing_env_file_is_empty(tmp_path):
    assert read_env_file(tmp_path / "nope.env") == {}


def test_real_environment_wins_over_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text("APT_HOME_KEY=from-file\n", encoding="utf-8")
    s = load_settings({"APT_HOME_KEY": "from-env"}, f)
    assert s.apt_home_key == "from-env"


def test_blank_values_become_none(tmp_path):
    f = tmp_path / ".env"
    f.write_text("RICHRICH_DATABASE_URL=\nAPT_DATABASE_URL=   \n", encoding="utf-8")
    s = load_settings({}, f)
    assert s.richrich_database_url is None
    assert s.apt_database_url is None
    assert s.apt_home_band is None


def test_rejects_unknown_home_band(tmp_path):
    with pytest.raises(ValueError, match="APT_HOME_BAND"):
        load_settings({"APT_HOME_BAND": "99"}, tmp_path / "none.env")


def test_owner_context_comes_from_env(tmp_path):
    s = load_settings({"HUB_OWNER_CONTEXT": "Korean investor in 분당"}, tmp_path / "none.env")
    assert s.owner_context == "Korean investor in 분당"
    assert load_settings({}, tmp_path / "none.env").owner_context is None


def test_news_aliases_and_areas(tmp_path):
    f = tmp_path / ".env"
    f.write_text("HUB_NEWS_ALIASES=tsla:테슬라, 일론; ARM:암;broken;X:\nHUB_NEWS_AREAS= 판교, 분당 ,,\n", encoding="utf-8")
    s = load_settings({}, f)
    assert s.news_aliases == (("TSLA", ("테슬라", "일론")), ("ARM", ("암",)))
    assert s.news_areas == ("판교", "분당")
    assert load_settings({}, tmp_path / "none.env").news_aliases == ()

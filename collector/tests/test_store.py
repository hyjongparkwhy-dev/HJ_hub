from hub_collect.embed import embedding_text
from hub_collect.normalize import Item
from hub_collect.store import vector_literal


def test_vector_literal_is_pgvector_text():
    assert vector_literal([0.5, -0.25, 1e-9]) == "[0.500000,-0.250000,0.000000]"


def test_embedding_text_uses_summary_when_present():
    base = Item("a", "invest", "https://a/1", "Fed holds", "fedholds", "", None)
    assert embedding_text(base) == "Fed holds"
    assert embedding_text(Item(**{**base.__dict__, "summary": "Rates unchanged"})) == "Fed holds. Rates unchanged"


def test_fetch_turns_http_protocol_errors_into_fetch_error(monkeypatch):
    import http.client

    import pytest

    from hub_collect import fetch as fetch_module

    def broken(*args, **kwargs):
        raise http.client.IncompleteRead(b"partial")

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", broken)
    with pytest.raises(fetch_module.FetchError, match="IncompleteRead"):
        fetch_module.fetch("https://example.com/rss")


def test_fetch_retries_once_after_a_transient_failure(monkeypatch):
    import io
    import urllib.error

    from hub_collect import fetch as fetch_module

    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError(TimeoutError("handshake timed out"))
        return io.BytesIO(b"<rss/>")

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", flaky)
    assert fetch_module.fetch("https://example.com/rss") == b"<rss/>"
    assert len(calls) == 2

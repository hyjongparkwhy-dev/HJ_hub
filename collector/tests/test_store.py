from hub_collect.embed import embedding_text
from hub_collect.normalize import Item
from hub_collect.store import vector_literal


def test_vector_literal_is_pgvector_text():
    assert vector_literal([0.5, -0.25, 1e-9]) == "[0.500000,-0.250000,0.000000]"


def test_embedding_text_uses_summary_when_present():
    base = Item("a", "invest", "https://a/1", "Fed holds", "fedholds", "", None)
    assert embedding_text(base) == "Fed holds"
    assert embedding_text(Item(**{**base.__dict__, "summary": "Rates unchanged"})) == "Fed holds. Rates unchanged"

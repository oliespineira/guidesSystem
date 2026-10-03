import pytest

from src.messaging import topics


@pytest.mark.parametrize("pattern, topic, expected", [
    ("ronda.5.all", "ronda.5.all", True),
    ("ronda.5.all", "ronda.6.all", False),
    ("ronda.5.#", "ronda.5.rama.guias", True),
    ("ronda.5.#", "ronda.6.all", False),
    ("ronda.5.rama.*", "ronda.5.rama.alitas", True),
    ("ronda.5.rama.*", "ronda.5.all", False),
    ("ronda.5", "ronda.5.all", False),          # a prefix is not a match
    ("ronda.5.all.x", "ronda.5.all", False),    # longer pattern than topic
])
def test_matches(pattern, topic, expected):
    assert topics.matches(pattern, topic) is expected


@pytest.mark.parametrize("name, expected", [
    ("Guías", "guias"),
    ("  GUIAS ", "guias"),
    ("Guías Mayores", "guias-mayores"),
    ("Alitas/Rangers", "alitas-rangers"),
])
def test_slug(name, expected):
    assert topics.slug(name) == expected


def test_topic_builders():
    assert topics.all_topic(5) == "ronda.5.all"
    assert topics.kraal_topic(5) == "ronda.5.kraal"
    assert topics.rama_topic(5, "Guías") == "ronda.5.rama.guias"
    assert topics.everything_in(5) == "ronda.5.#"
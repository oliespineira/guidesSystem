import pytest

from src.messaging import topics
from src.errors import InvalidInputError


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
    assert topics.rama_topic(5, "Guías") == "ronda.5.rama.guias"
    assert topics.role_topic(5, "Tesorera") == "ronda.5.role.tesorera"

@pytest.mark.parametrize("audience, target, expected", [
    ("all", None, "ronda.5.all"),
    ("rama", "Guías", "ronda.5.rama.guias"),
    ("role", "Tesorera", "ronda.5.role.tesorera"),
])
def test_notice_topic(audience, target, expected):
    assert topics.notice_topic(5, audience, target) == expected


@pytest.mark.parametrize("audience, target", [("rama", None), ("role", "  "), ("everyone", "x")])
def test_notice_topic_rejects_bad_input(audience, target):
    with pytest.raises(InvalidInputError):
        topics.notice_topic(5, audience, target)
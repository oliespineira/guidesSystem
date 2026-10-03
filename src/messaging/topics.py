import re
import unicodedata


def slug(name: str) -> str:
    """'Guías Mayores' -> 'guias-mayores'. Topics use slugs so accents, spaces
    and capital letters never stop a notice from reaching the right rama."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def all_topic(ronda_id: int) -> str:
    return f"ronda.{ronda_id}.all"




def rama_topic(ronda_id: int, rama_name: str) -> str:
    return f"ronda.{ronda_id}.rama.{slug(rama_name)}"


def role_topic(ronda_id: int, role_name: str) -> str:
    return f"ronda.{ronda_id}.role.{slug(role_name)}"

def matches(pattern: str, topic: str) -> bool:
    """'*' matches exactly one segment, '#' matches everything after it."""
    p, t = pattern.split("."), topic.split(".")
    for i, seg in enumerate(p):
        if seg == "#":
            return True
        if i >= len(t) or (seg != "*" and seg != t[i]):
            return False
    return len(p) == len(t)
import re
import unicodedata

from app.errors import InvalidInputError


def slug(name: str) -> str:
    """'Guías Mayores' -> 'guias-mayores'. Topics use slugs so accents, spaces
    and capital letters never stop a notice from reaching the right rama."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def require_text(value: str | None, field: str) -> str:
    """Return the stripped value, or raise if it is missing or blank."""
    if value is None or not value.strip():
        raise InvalidInputError(f"{field} cannot be empty")
    return value.strip()

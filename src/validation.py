from src.errors import InvalidInputError
def require_text(value: str|None, field:str)-> str:
    """Return the stripped value, or raise if it is missing or blank."""
    if value is None or not value.strip():
        raise InvalidInputError(f"{field} cannot be empty")
    return value.strip()    
"""
These keep the service layer free of web code; services raise plain Python excenmptions that carry a staatus code as data. Handlers in the code will convert them into HTTP responses.
"""

class DomainError(ValueError):
    """Base for all business-rule failures. Carries the HTTP status the API should use."""
    status_code = 400


class InvalidInputError(DomainError):
    status_code = 400


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409
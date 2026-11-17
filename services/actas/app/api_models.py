from pydantic import BaseModel


class ErrorOut(BaseModel):
    detail: str


class CreatedOut(BaseModel):
    id: int


class HealthOut(BaseModel):
    status: str
    db: str
    version: str


ERROR_RESPONSES = {
    400: {"model": ErrorOut, "description": "Invalid input"},
    403: {"model": ErrorOut, "description": "Not allowed (for example, not the treasurer)"},
    404: {"model": ErrorOut, "description": "Not found"},
    409: {"model": ErrorOut, "description": "Conflict with existing data"},
    503: {"model": ErrorOut, "description": "The kraal service is unavailable"},
}

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
    404: {"model": ErrorOut, "description": "Not found"},
    409: {"model": ErrorOut, "description": "Conflict with existing data"},
}

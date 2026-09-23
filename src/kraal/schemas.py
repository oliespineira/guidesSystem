from datetime import date
from pydantic import BaseModel, Field #pydantic checks shape  and the service checks business rules

class RondaCreate(BaseModel):
    year_label: str = Field(..., min_length=1)
    start_date: date

class VolunteerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    joined_date: date | None = None

class RoleAssign(BaseModel):
    volunteer_id: int
    role_name: str = Field(..., min_length=1)

class RamaCreate(BaseModel):
    name: str = Field(..., min_length=1)

class RamaMember(BaseModel):
    volunteer_id: int
    availability_pct: int | None = None    # range checked in the service, not here
    notes: str | None = None
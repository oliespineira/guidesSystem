from datetime import date
from pydantic import BaseModel, Field

class MeetingCreate(BaseModel):
    ronda_id:int
    date:date
    title:str = Field(..., min_length=1)

class AgendaItemCreate(BaseModel):
    section_title:str = Field(..., min_length=1)
    content:str| None=None
    position: int|None= None

class DecisionCreate(BaseModel):
    description:str= Field(..., min_length=1)
    vote_result:str| None=None

class CalendarEventCreate(BaseModel):
    ronda_id: int
    start_date:date
    activity_type: str= Field(..., min_length=1)
    end_date: date| None=None
    assigned_volunteers: str| None=None
class BudgetCreate(BaseModel):
    ronda_id: int
    category: str = Field(..., min_length=1)
    allocated_cents: int                     # sign checked in the service


class RequestCreate(BaseModel):
    rama: str = Field(..., min_length=1)
    item: str = Field(..., min_length=1)
    amount_cents: int                        # > 0 checked in the service


class RequestAction(BaseModel):
    actor: str | None = None
    note: str | None = None


class RequestPayment(RequestAction):
    payment_ref: str = Field(..., min_length=1)

class VoteOpen(BaseModel):
    closes_at: str                         # ISO date-time, parsed and checked in the service
    rule: str = "majority_of_cast"


class VoteCast(BaseModel):
    volunteer_id: int
    choice: str                            # yes | no | abstain, checked in the service

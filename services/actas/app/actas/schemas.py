from datetime import date

from pydantic import BaseModel, Field

# Every max_length matches the column's NVARCHAR(n) in migrations/001_init.sql, so a value that is
# too long gets a clear 422 here instead of a 500 from the database. NVARCHAR(MAX) columns
# (agenda content) have no limit.


class MeetingCreate(BaseModel):
    ronda_id: int
    date: date
    title: str = Field(..., min_length=1, max_length=200)


class AgendaItemCreate(BaseModel):
    section_title: str = Field(..., min_length=1, max_length=200)
    content: str | None = None
    position: int | None = None


class DecisionCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=1000)
    vote_result: str | None = Field(None, max_length=500)


class CalendarEventCreate(BaseModel):
    ronda_id: int
    start_date: date
    activity_type: str = Field(..., min_length=1, max_length=100)
    end_date: date | None = None
    assigned_volunteers: str | None = Field(None, max_length=1000)


class BudgetCreate(BaseModel):
    ronda_id: int
    category: str = Field(..., min_length=1, max_length=100)
    allocated_cents: int  # sign checked in the service


class RequestCreate(BaseModel):
    rama: str = Field(..., min_length=1, max_length=100)
    item: str = Field(..., min_length=1, max_length=200)
    amount_cents: int  # > 0 checked in the service


class RequestAction(BaseModel):
    volunteer_id: int  # who is acting; the service checks they hold the treasurer role
    note: str | None = Field(None, max_length=1000)


class RequestPayment(RequestAction):
    payment_ref: str = Field(..., min_length=1, max_length=100)


class VoteOpen(BaseModel):
    closes_at: str  # ISO date-time, parsed and checked in the service
    rule: str = "majority_of_cast"  # checked against the known rules in the service


class VoteCast(BaseModel):
    volunteer_id: int
    choice: str  # yes | no | abstain, checked in the service


class BookingPlan(BaseModel):
    book_by: str | None = None  # default: start date minus BOOKING_LEAD_DAYS


class BookingDone(BaseModel):
    venue: str = Field(..., min_length=1, max_length=200)
    request_id: int | None = None  # the tesorería request that paid for it, if any

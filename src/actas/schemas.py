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



from pydantic import BaseModel, Field

class NoticeCreate(BaseModel):
    ronda_id: int
    audience:str= "all"
    target:str|None=None
    title:str = Field(..., min_length=1)
    body:str| None=None
from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    ronda_id: int
    audience: str = "all"  # all | rama | role, checked when the topic is built
    target: str | None = Field(None, max_length=100)  # a rama or role name, same limit as in kraal
    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = None  # NVARCHAR(MAX): no limit

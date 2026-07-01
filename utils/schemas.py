# utils/types.py
from typing import Literal, Optional
from pydantic import BaseModel

class RouterDecision(BaseModel):
    route: Literal["tarot", "zodiac", "bazi", "clarify", "out_of_scope"]
    rationale: str
    message_to_user: str

class ConciergeResult(BaseModel):
    route: str
    concierge_message: str
    reading: Optional[str] = None
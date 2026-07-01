# utils/schemas.py
from typing import Literal, Optional
from pydantic import BaseModel, Field

# The routes the Concierge can choose. Defined once and reused so the set can
# never drift between the router schema and the result schema.
Route = Literal["tarot", "zodiac", "bazi", "clarify", "out_of_scope"]

# How a single turn can end.
#   reading / need_input  -> come from a specialist
#   clarify / out_of_scope -> come straight from the router (no specialist runs)
TurnStatus = Literal["reading", "need_input", "clarify", "out_of_scope"]


class RouterDecision(BaseModel):
    """The Concierge's routing choice.

    LLM-generated and guaranteed to be valid by passing this model as
    `response_schema` in route_request().
    """
    route: Route
    rationale: str
    message_to_user: str


class SpecialistReply(BaseModel):
    """What every specialist's run() returns.

    This is the fix for the one-shot-vs-conversational ambiguity: it lets a
    specialist say "here is the reading" OR "I need more from you first" in a
    way the orchestrator and memory can tell apart.

        status == "reading"     -> `text` is the finished reading
        status == "need_input"  -> `text` is the question to ask the user,
                                    and `missing` names the fields still needed
    """
    status: Literal["reading", "need_input"]
    text: str
    missing: list[str] = Field(default_factory=list)


class ConciergeResult(BaseModel):
    """The terminal result of one concierge turn. The app switches on `status`.

    Field usage by status:
        reading      -> concierge_message = the router's warm handoff line
                        reading           = the actual reading (log THIS to memory)
        need_input   -> concierge_message = the specialist's question to the user
                        reading           = None
                        missing           = fields still needed
        clarify      -> concierge_message = the single clarifying question
        out_of_scope -> concierge_message = the gentle redirect
    """
    route: Route
    status: TurnStatus          # required on purpose: no silent default to "reading"
    concierge_message: str
    reading: Optional[str] = None
    missing: list[str] = Field(default_factory=list)

    @property
    def is_reading(self) -> bool:
        """The one gate memory should check before calling add_reading()."""
        return self.status == "reading"
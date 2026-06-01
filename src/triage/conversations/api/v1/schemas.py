"""Request/response DTOs for the v1 API (distinct from internal domain models)."""

from pydantic import BaseModel, Field

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.schemas import DecisionPacket


class CreateConversationRequest(BaseModel):
    customer_id: str = Field(min_length=1)


class CreateConversationResponse(BaseModel):
    conversation_id: str
    status: ConversationStatus


class MessageRequest(BaseModel):
    text: str = Field(min_length=1)


class MessageResponse(BaseModel):
    conversation_id: str
    status: ConversationStatus
    clarification: str | None = None
    decision: DecisionPacket | None = None


class ConversationResponse(BaseModel):
    conversation_id: str
    status: ConversationStatus
    clarification: str | None = None
    decision: DecisionPacket | None = None

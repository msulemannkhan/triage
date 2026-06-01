"""Feature-level dependency wiring."""

from fastapi import Request

from .services.conversation_service import ConversationService


def get_service(request: Request) -> ConversationService:
    return request.app.state.service

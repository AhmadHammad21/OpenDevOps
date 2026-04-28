"""Request and response models for the chat endpoint."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str

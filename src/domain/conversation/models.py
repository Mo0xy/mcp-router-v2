# src/domain/conversation/models.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from src.domain.chat.models import ConversationState


class ConversationSession(BaseModel):
    """
    Rappresenta una sessione di conversazione persistente.

    Estende ConversationState aggiungendo:
    - ID univoco per tracciamento
    - Timestamp di creazione/ultimo aggiornamento
    - Metadata per user tracking
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: ConversationState
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None  # per multi-user in futuro
    metadata: dict = Field(default_factory=dict)

    def update_state(self, new_state: ConversationState) -> None:
        """Aggiorna lo state e il timestamp."""
        self.state = new_state
        self.updated_at = datetime.now()

    def get_id(self):
        """Restituisce l'id della conversatione """
        return self.id

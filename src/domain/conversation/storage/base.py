# src/domain/conversation/storage/base.py
from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.conversation.models import ConversationSession


class ConversationStorage(ABC):
    """Interface per storage delle conversazioni."""

    @abstractmethod
    async def save(self, session: ConversationSession) -> None:
        """Salva o aggiorna una conversazione."""
        pass

    @abstractmethod
    async def load(self, conversation_id: str) -> Optional[ConversationSession]:
        """Carica una conversazione per ID."""
        pass

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool:
        """Elimina una conversazione."""
        pass

    @abstractmethod
    async def list_all(self, user_id: Optional[str] = None) -> List[ConversationSession]:
        """Lista tutte le conversazioni (filtrate per user_id se fornito)."""
        pass
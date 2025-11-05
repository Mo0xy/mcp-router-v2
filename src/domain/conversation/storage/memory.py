# src/domain/conversation/storage/memory.py
from typing import Optional, List, Dict
from src.domain.conversation.storage.base import ConversationStorage
from src.domain.conversation.models import ConversationSession
import logging

logger = logging.getLogger(__name__)


class InMemoryConversationStorage(ConversationStorage):
    """
    Storage in-memory per conversazioni (MVP).

    Pro:
    - Semplice implementazione
    - Zero dipendenze esterne
    - Veloce per testing/development

    Con:
    - Dati persi al restart dell'app
    - Non scalabile per produzione multi-istanza

    Use case: MVP, testing, single-user CLI
    """

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}
        logger.info("InMemoryConversationStorage initialized")

    async def save(self, session: ConversationSession) -> None:
        """Salva conversazione in memoria."""
        self._sessions[session.id] = session
        logger.debug(f"Saved conversation {session.id}")

    async def load(self, conversation_id: str) -> Optional[ConversationSession]:
        """Carica conversazione per ID."""
        session = self._sessions.get(conversation_id)
        if session:
            logger.debug(f"Loaded conversation {conversation_id}")
        else:
            logger.debug(f"Conversation {conversation_id} not found")
        return session

    async def delete(self, conversation_id: str) -> bool:
        """Elimina conversazione."""
        if conversation_id in self._sessions:
            del self._sessions[conversation_id]
            logger.debug(f"Deleted conversation {conversation_id}")
            return True
        return False

    async def list_all(self, user_id: Optional[str] = None) -> List[ConversationSession]:
        """Lista conversazioni."""
        sessions = list(self._sessions.values())

        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]

        logger.debug(f"Listed {len(sessions)} conversations")
        return sessions

    def clear_all(self) -> None:
        """Utility per testing: cancella tutto."""
        self._sessions.clear()
        logger.debug("Cleared all conversations")
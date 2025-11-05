# src/domain/conversation/manager.py
from typing import Optional
import logging

from src.domain.conversation.models import ConversationSession
from src.domain.conversation.storage.base import ConversationStorage
from src.domain.chat.models import ConversationState
from src.shared.exceptions import MCPRouterException

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Gestisce il ciclo di vita delle conversazioni.

    Responsabilità:
    - Creazione nuove conversazioni
    - Recupero conversazioni esistenti
    - Salvataggio/aggiornamento state
    - Eliminazione conversazioni

    Usa un'interfaccia Storage per la persistenza,
    permettendo diverse implementazioni (memory, file, DB).
    """

    def __init__(self, storage: ConversationStorage):
        """
        Args:
            storage: Implementazione dello storage
        """
        self.storage = storage
        logger.info(f"ConversationManager initialized with {type(storage).__name__}")

    async def create_conversation(
            self,
            initial_state: Optional[ConversationState] = None,
            user_id: Optional[str] = None,
            metadata: Optional[dict] = None
    ) -> ConversationSession:
        """
        Crea una nuova conversazione.

        Args:
            initial_state: State iniziale (opzionale)
            user_id: ID utente (opzionale, per multi-user)
            metadata: Metadata aggiuntivi

        Returns:
            Nuova ConversationSession
        """
        session = ConversationSession(
            state=initial_state or ConversationState(),
            user_id=user_id,
            metadata=metadata or {}
        )

        await self.storage.save(session)
        logger.info(f"Created conversation {session.id}")
        return session

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationSession]:
        """
        Recupera una conversazione esistente.

        Args:
            conversation_id: ID della conversazione

        Returns:
            ConversationSession se trovata, None altrimenti
        """
        session = await self.storage.load(conversation_id)

        if session:
            logger.debug(f"Retrieved conversation {conversation_id}")
        else:
            logger.warning(f"Conversation {conversation_id} not found")

        return session

    async def update_conversation(
            self,
            conversation_id: str,
            new_state: ConversationState
    ) -> ConversationSession:
        """
        Aggiorna lo state di una conversazione esistente.

        Args:
            conversation_id: ID della conversazione
            new_state: Nuovo state

        Returns:
            ConversationSession aggiornata

        Raises:
            MCPRouterException: Se conversazione non trovata
        """
        session = await self.get_conversation(conversation_id)

        if not session:
            raise MCPRouterException(
                f"Conversation {conversation_id} not found",
                details={"conversation_id": conversation_id}
            )

        session.update_state(new_state)
        await self.storage.save(session)
        logger.info(f"Updated conversation {conversation_id}")
        return session

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Elimina una conversazione.

        Args:
            conversation_id: ID della conversazione

        Returns:
            True se eliminata, False se non trovata
        """
        result = await self.storage.delete(conversation_id)

        if result:
            logger.info(f"Deleted conversation {conversation_id}")
        else:
            logger.warning(f"Conversation {conversation_id} not found for deletion")

        return result

    async def list_conversations(self, user_id: Optional[str] = None):
        """Lista conversazioni (opzionalmente filtrate per user_id)."""
        return await self.storage.list_all(user_id)
"""
CLI Adapter - Adapter between CLI interface and ChatService.

Location: src/infrastructure/cli/adapter.py

This adapter translates CLI-specific functionality into
calls to the domain ChatService, following the Adapter Pattern.

REFACTORING FROM V1:
- V1: CliChat class mixed presentation and business logic
- V2: Clean separation:
  * CliAdapter: CLI-specific adaptations
  * ChatService: Pure business logic (domain layer)
"""

import logging
from typing import Dict, List, Any, Optional
from src.domain.chat.service import ChatService
from src.domain.chat.models import UserChatRequest, ChatResponse
from src.domain.mcp.client import MCPClient
from src.domain.conversation.manager import ConversationManager
from src.shared.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class CliAdapter:
    """
    Adapter for CLI-specific chat functionality.

    This class wraps ChatService and adds CLI-specific features like:
    - Resource extraction from @ mentions
    - Prompt handling with / commands
    - Enhanced terminal output
    """

    def __init__(
            self,
            chat_service: ChatService,
            mcp_clients: Dict[str, MCPClient],
            conversation_manager: ConversationManager,
    ):
        """
        Initialize CLI adapter.

        Args:
            chat_service: Core chat service (domain layer)
            mcp_clients: Dictionary of MCP clients by name
        """
        self.current_conversation = None
        self.chat_service = chat_service
        self.mcp_clients = mcp_clients
        self.conversation_manager = conversation_manager
        logger.info("CLI Adapter base params initialized")

    async def initialize(self):
        self.current_conversation = await self.conversation_manager.create_conversation()
        logger.info("Conversation Initialized")
        logger.info("CLI initialization completed")

    # ========================================================================
    # Main Chat Method
    # ========================================================================

    async def process_message(self, message: str) -> ChatResponse:
        """
        Process a user message from CLI.

        This method:
        1. Extracts resources if @ mentions are present
        2. Handles / prompt commands
        3. Delegates to ChatService for actual processing

        Args:
            user_input: Raw user input from CLI

        Returns:
            AI response string
            :param message:
        """

        try:
            user_query: UserChatRequest = UserChatRequest(
                query=message,
                max_iterations=5,
                temperature=0.4,
                max_tokens=10000,
            )

            # Check for resource mentions (@)
            if "@" in user_query.query:
                user_query.query = await self._extract_resources(user_query.query)

            # Check for prompt commands (/)
            if user_query.query.startswith("/"):
                return await self._handle_prompt_command(user_query.query)

            # Regular chat processing
            return await (
                self.chat_service.process_query(
                    user_query,
                    conversation_id=self.current_conversation.id))

        except Exception as e:
            logger.error(f"Error processing CLI message: {e}")
            return f"Error: {e}"

    # ========================================================================
    # Resource Extraction (@ mentions)
    # ========================================================================

    async def _extract_resources(self, query: str) -> str:
        """
        Extract and load resources mentioned with @.

        Example: "Summarize @report.pdf" -> loads report.pdf content

        Args:
            query: User query with @ mentions

        Returns:
            Modified query with resource content embedded
        """
        logger.info(f"Extracting resources from: {query}")

        # Find all @ mentions
        import re
        mentions = re.findall(r'@([\w\-\.]+)', query)

        if not mentions:
            return query

        # Load each resource
        loaded_resources = []
        for mention in mentions:
            try:
                # Try to find matching resource across all clients
                resource_uri = await self._find_resource_uri(mention)
                if resource_uri:
                    content = await self._read_resource(resource_uri)
                    loaded_resources.append(f"\n[Resource: {mention}]\n{content}\n")
            except Exception as e:
                logger.warning(f"Could not load resource {mention}: {e}")
                loaded_resources.append(f"\n[Resource {mention} not found]\n")

        # Build enhanced query
        resources_text = "".join(loaded_resources)
        clean_query = re.sub(r'@[\w\-\.]+', '', query).strip()

        return f"{resources_text}\n\nUser query: {clean_query}"

    async def _find_resource_uri(self, mention: str) -> Optional[str]:
        """
        Find the URI for a resource mention.

        Args:
            mention: Resource mention (e.g., "report.pdf")

        Returns:
            Resource URI or None
        """
        for client_name, client in self.mcp_clients.items():
            try:
                resources = await client.list_resources()
                for resource in resources:
                    if mention.lower() in resource.get("name", "").lower():
                        return resource.get("uri")
            except Exception as e:
                logger.warning(f"Error listing resources from {client_name}: {e}")

        return None

    async def _read_resource(self, uri: str) -> str:
        """
        Read resource content by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource content as string
        """
        for client_name, client in self.mcp_clients.items():
            try:
                content = await client.read_resource(uri)
                return str(content)
            except Exception:
                continue

        raise ToolExecutionError(f"Could not read resource: {uri}")

    # ========================================================================
    # Prompt Commands (/ commands)
    # ========================================================================

    async def _handle_prompt_command(self, command: str) -> ChatResponse:
        """
        Handle / prompt commands.

        Example: /summarize doc_123

        Args:
            command: Command string starting with /

        Returns:
            AI response
        """
        # Parse command
        parts = command.split(maxsplit=1)
        cmd_name = parts[0][1:]  # Remove /
        args = parts[1] if len(parts) > 1 else ""

        logger.info(f"Executing prompt command: {cmd_name} with args: {args}")

        # Find prompt in MCP clients
        for client_name, client in self.mcp_clients.items():
            try:
                prompts = await client.list_prompts()

                # Find matching prompt
                for prompt in prompts:
                    if prompt.name == cmd_name:
                        # Execute prompt
                        messages = await client.get_prompt(
                            cmd_name,
                            {"doc_id": args} if args else {}
                        )

                        # Convert prompt messages to query
                        query = "\n".join([msg.content.text for msg in messages if hasattr(msg.content, 'text')])

                        return await self.chat_service.process_query(query)
            except Exception as e:
                logger.warning(f"Error executing prompt in {client_name}: {e}")

        return f"Prompt '/{cmd_name}' not found"

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def list_available_tools(self) -> List[str]:
        """
        List all available tools.

        Returns:
            List of tool names
        """
        return await self.chat_service.list_available_tools()

    async def list_available_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources.

        Returns:
            List of resource metadata dicts
        """
        return await self.chat_service.list_available_resources()

    async def list_available_prompts(self) -> List[Any]:
        """
        List all available prompts.

        Returns:
            List of prompt objects
        """
        return await self.chat_service.list_available_prompts()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get current conversation history.

        Returns:
            List of message dicts
        """
        return self.chat_service.messages

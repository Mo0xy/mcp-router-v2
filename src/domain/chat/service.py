"""
Chat Service - Core business logic for chat functionality.

This service unifies the logic from V1's Chat and CliChat classes,
providing a clean, testable interface for processing chat queries
with tool execution and resource management.

REFACTORING FROM V1:
- V1: Chat class + CliChat class (duplicated logic)
- V2: Single ChatService with dependency injection
- Separation: Business logic (here) vs Presentation (CLI adapter)
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

from src.domain.chat.models import (
    UserChatRequest,
    ChatResponse,
    ConversationState,
    ResourceReference,
)
from src.domain.tools.manager import ToolManager
from src.domain.mcp.protocols import MCPClientProtocol
from src.infrastructure.llm.base import LLMProvider
from src.infrastructure.llm.models import LLMResponse
from src.infrastructure.llm.message_converter import MessageConverter
from src.shared.exceptions import (
    MCPRouterException,
    ToolExecutionError,
    ResourceNotFoundException,
)
from src.shared.constants import (
    MAX_CONVERSATION_ITERATIONS,
    STOP_REASON_END_TURN,
    STOP_REASON_TOOL_USE,
)

logger = logging.getLogger(__name__)


class ChatService:
    """
    Core chat service handling conversation logic.

    This service orchestrates:
    - LLM interactions
    - Tool discovery and execution
    - Resource loading
    - Conversation state management
    """

    def __init__(
            self,
            llm_provider: LLMProvider,
            tool_manager: ToolManager,
            mcp_clients: Dict[str, MCPClientProtocol],
            default_max_iterations: int = 5,
            default_temperature: float = 0.4,
            default_max_tokens: int = 10000,
    ):
        """
        Initialize chat service.

        Args:
            llm_provider: LLM provider for model interactions
            tool_manager: Tool manager for tool operations
            mcp_clients: Dictionary of MCP clients
            default_max_iterations: Default max conversation iterations
            default_temperature: Default LLM temperature
            default_max_tokens: Default max tokens to generate
        """
        self.llm_provider = llm_provider
        self.tool_manager = tool_manager
        self.mcp_clients = mcp_clients
        self.default_max_iterations = default_max_iterations
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    # ========================================================================
    # Main Processing Logic
    # ========================================================================

    async def process_query(self, request: UserChatRequest) -> ChatResponse:
        """
        Process a chat query end-to-end.

        This is the main entry point that orchestrates the entire
        conversation flow including tool execution.

        Args:
            request: Chat request with query and parameters

        Returns:
            Chat response with final answer

        Raises:
            MCPRouterException: If processing fails
        """
        logger.info(f"Processing query: {request.query[:100]}...")

        # Initialize conversation state
        conversation = ConversationState(
            max_iterations=request.max_iterations or self.default_max_iterations
        )

        # Extract and load any resources mentioned in the query
        query_with_resources = await self._process_resources(request.query)

        # Add initial user message
        conversation.add_message("user", query_with_resources)

        # Get available tools
        available_tools = await self.tool_manager.get_all_tools()
        logger.debug(f"Available tools: {[t['name'] for t in available_tools]}")

        # Main conversation loop
        total_tools_called = 0
        final_text_response = ""

        while not conversation.is_complete:
            conversation.increment_iteration()

            logger.info(
                f"Iteration {conversation.iteration_count}/{conversation.max_iterations}"
            )

            try:
                # Call LLM
                llm_response = await self._call_llm(
                    messages=conversation.get_messages_for_llm(),
                    tools=available_tools,
                    temperature=request.temperature or self.default_temperature,
                    max_tokens=request.max_tokens or self.default_max_tokens,
                )

                # Add assistant response to conversation
                assistant_message = MessageConverter.create_assistant_message(llm_response)
                conversation.add_message(
                    "assistant",
                    self._message_content_to_str(assistant_message["content"]),
                )

                # Extract text response
                text_response = llm_response.get_text()
                logger.info(f"getting llm response..\n{llm_response}")
                if text_response:
                    final_text_response = text_response
                    logger.info(f"\nLLM text response: {text_response[:100]}...")

                if llm_response.stop_reason == 'end_turn':
                    final_text_response = text_response
                    break

                # Check stop reason
                logger.info(f"Stop reason: {llm_response.stop_reason}")
                logger.info(f"has tool calls: {llm_response.has_tool_calls()}")

                # Handle tool calls
                if llm_response.has_tool_calls():
                    tool_calls = llm_response.get_tool_calls()
                    logger.info(f"Executing {len(tool_calls)} tool(s)")

                    # Execute tools
                    tool_results = await self.tool_manager.execute_tool_calls(
                        [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "input": tc.input,
                            }
                            for tc in tool_calls
                        ]
                    )

                    total_tools_called += len(tool_calls)
                    logger.info(f"tool_result in service: {tool_results}")


                    # Add tool results to conversation
                    tool_result_message = MessageConverter.create_tool_result_message(
                        tool_results
                    )
                    logger.info(f"tool result message: {tool_result_message}")
                    logger.info(f"tool result message content: {tool_result_message.get("content")}")

                    conversation.add_message(
                        "user",
                        self._message_content_to_str(tool_result_message["content"]),
                        metadata={"tool_results": True},
                    )

                    logger.info(f"\nconversation state:\n{conversation}")

                    # Continue loop for next iteration
                    continue

                # No more tool calls - conversation complete
                logger.info("Conversation complete (no more tool calls)")
                conversation.is_complete = True

            except ToolExecutionError as e:
                logger.error(f"Tool execution error: {e}")
                # Continue with partial results
                if final_text_response:
                    conversation.is_complete = True
                else:
                    raise

            except Exception as e:
                logger.exception(f"Error in conversation iteration: {e}")
                raise MCPRouterException(
                    f"Conversation processing failed: {e}",
                    details={"iteration": conversation.iteration_count},
                )

        # Build final response
        logger.info(
            f"Query processed: {conversation.iteration_count} iterations, "
            f"{total_tools_called} tools called"
        )

        return ChatResponse(
            response=final_text_response or "No response generated",
            iterations_used=conversation.iteration_count,
            tools_called=total_tools_called,
            conversation_state=conversation,
            metadata={
                "max_iterations_reached": conversation.iteration_count
                                          >= conversation.max_iterations,
            },
        )

    # ========================================================================
    # LLM Interaction
    # ========================================================================

    async def _call_llm(
            self,
            messages: List[Dict[str, Any]],
            tools: List[Dict[str, Any]],
            temperature: float,
            max_tokens: int,
    ) -> LLMResponse:
        """
        Call LLM with retry logic.

        Args:
            messages: Conversation messages
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLM response
        """
        return await self.llm_provider.chat_with_retry(
            messages=messages,
            tools=tools if tools else None,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=3,
        )

    # ========================================================================
    # Resource Handling
    # ========================================================================

    async def _process_resources(self, query: str) -> str:
        """
        Extract and load resources mentioned in the query.

        Resources are referenced with @ prefix (e.g., @document_id).

        Args:
            query: Original query with potential resource references

        Returns:
            Query with resource contents embedded
        """
        # Extract resource references
        resource_refs = ResourceReference.parse_from_query(query)

        if not resource_refs:
            logger.debug("No resource references found in query")
            return query

        logger.info(f"Found {len(resource_refs)} resource reference(s)")

        # Load resources
        loaded_resources: Dict[str, str] = {}

        for ref in resource_refs:
            try:
                content = await self._load_resource(ref.resource_id)
                loaded_resources[ref.resource_id] = content
                logger.debug(f"Loaded resource: {ref.resource_id}")
            except ResourceNotFoundException:
                logger.warning(f"Resource not found: {ref.resource_id}")
                loaded_resources[ref.resource_id] = f"[Resource {ref.resource_id} not found]"
            except Exception as e:
                logger.error(f"Error loading resource {ref.resource_id}: {e}")
                loaded_resources[ref.resource_id] = f"[Error loading {ref.resource_id}]"

        # Replace resource references with content
        processed_query = query
        for ref in resource_refs:
            content = loaded_resources.get(ref.resource_id, "")
            replacement = f"\n\n--- Content of {ref.resource_id} ---\n{content}\n--- End of {ref.resource_id} ---\n"
            processed_query = processed_query.replace(ref.raw_reference, replacement)

        return processed_query

    async def _load_resource(self, resource_id: str) -> str:
        """
        Load a resource by ID from MCP clients.

        Args:
            resource_id: Resource identifier

        Returns:
            Resource content as string

        Raises:
            ResourceNotFoundException: If resource not found
        """
        for client_name, client in self.mcp_clients.items():
            try:
                # Try to read as URI
                content = await client.read_resource(f"resource://{resource_id}")
                return str(content)
            except Exception:
                # Try next client
                continue

        raise ResourceNotFoundException(
            f"Resource '{resource_id}' not found",
            details={"resource_id": resource_id},
        )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _message_content_to_str(self, content: Any) -> str:
        """
        Convert message content to string for storage.

        Args:
            content: Message content (string or structured)

        Returns:
            String representation
        """

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # For structured content, just store a placeholder
            return str(content)
        else:
            return str(content)

    # ========================================================================
    # Additional Capabilities (from CliChat)
    # ========================================================================

    async def list_available_tools(self) -> List[str]:
        """
        List names of all available tools.

        Returns:
            List of tool names
        """
        tools = await self.tool_manager.get_all_tools()
        return [tool["name"] for tool in tools]

    async def list_available_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources from all MCP clients.

        Returns:
            List of resource metadata
        """
        all_resources = []

        for client_name, client in self.mcp_clients.items():
            try:
                resources = await client.list_resources()
                all_resources.extend(resources)
            except Exception as e:
                logger.warning(f"Failed to list resources from {client_name}: {e}")

        return all_resources

    async def list_available_prompts(self) -> List[Any]:
        """
        List all available prompts from MCP clients.

        Returns:
            List of prompt objects
        """
        all_prompts = []

        for client_name, client in self.mcp_clients.items():
            try:
                prompts = await client.list_prompts()
                all_prompts.extend(prompts)
            except Exception as e:
                logger.warning(f"Failed to list prompts from {client_name}: {e}")

        return all_prompts
"""
Message Converter - Centralized message format conversion.

This module eliminates code duplication by providing a single source of truth
for converting between different message formats (internal, OpenRouter, MCP, etc.).

BEFORE: Conversion logic was scattered across multiple files (openrouter.py, chat.py)
AFTER: All conversion logic is centralized here
"""
import logging
import sys
from typing import List, Dict, Any, Union, Optional
from src.infrastructure.llm.models import (
    Message,
    ContentBlock,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    LLMResponse,
    content_to_text,
)
from src.shared.exceptions import MessageFormatError
from src.shared.constants import (
    ROLE_USER,
    ROLE_ASSISTANT,
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_TOOL_USE,
    CONTENT_TYPE_TOOL_RESULT,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # MCP requires stdout only for JSONRPC messages
)
logger = logging.getLogger(__name__)


class MessageConverter:
    """
    Centralized message conversion utility.

    This class provides static methods for converting between various message formats,
    eliminating duplicated conversion logic throughout the codebase.
    """

    # ========================================================================
    # Content Extraction
    # ========================================================================

    @staticmethod
    def extract_text_from_content(
            content: Union[str, List[Dict[str, Any]], List[ContentBlock]]
    ) -> str:
        """
        Extract plain text from various content formats.

        This replaces the duplicated logic in:
        - openrouter.py: _extract_text_from_content()
        - chat.py: text_from_message()

        Args:
            content: Content in various formats

        Returns:
            Extracted text as string

        Examples:
            >>> MessageConverter.extract_text_from_content("Hello")
            'Hello'

            >>> MessageConverter.extract_text_from_content([
            ...     {"type": "text", "text": "Hello"},
            ...     {"type": "text", "text": "World"}
            ... ])
            'Hello World'
        """
        return content_to_text(content)

    @staticmethod
    def extract_tool_calls(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from content blocks.

        Args:
            content: List of content blocks

        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == CONTENT_TYPE_TOOL_USE:
                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    }
                )
        return tool_calls

    # ========================================================================
    # OpenRouter Format Conversion
    # ========================================================================

    @staticmethod
    def to_openrouter_message(message: Union[Message, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert internal message format to OpenRouter API format.

        Args:
            message: Message in internal format

        Returns:
            Message in OpenRouter format

        Raises:
            MessageFormatError: If message format is invalid
        """
        if isinstance(message, Message):
            return {
                "role": message.role,
                "content": MessageConverter._normalize_content(message.content),
            }

        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")

            if not role:
                raise MessageFormatError("Message must have a 'role' field")

            return {
                "role": role,
                "content": MessageConverter._normalize_content(content),
            }

        raise MessageFormatError(f"Invalid message type: {type(message)}")

    @staticmethod
    def to_openrouter_messages(
            messages: List[Union[Message, Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Convert list of messages to OpenRouter format.

        Args:
            messages: List of messages in internal format

        Returns:
            List of messages in OpenRouter format
        """
        return [MessageConverter.to_openrouter_message(msg) for msg in messages]

    @staticmethod
    def from_openrouter_response(response_data: Dict[str, Any]) -> LLMResponse:
        """
        Convert OpenRouter API response to internal LLMResponse format.

        Args:
            response_data: Raw response from OpenRouter API

        Returns:
            Structured LLMResponse object

        Raises:
            MessageFormatError: If response format is invalid
        """
        try:
            choices = response_data.get("choices", [])
            if not choices:
                raise MessageFormatError("No choices in OpenRouter response")

            first_choice = choices[0]
            message = first_choice.get("message", {})
            content = message.get("content", "")

            # Normalize content to list of blocks
            if isinstance(content, str):
                content_blocks = [{"type": CONTENT_TYPE_TEXT, "text": content}]
            elif isinstance(content, list):
                content_blocks = content
            else:
                content_blocks = [{"type": CONTENT_TYPE_TEXT, "text": str(content)}]

            # AGGIUNGI QUESTA PARTE PER ESTRARRE LE TOOL CALLS
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                for tool_call in tool_calls:
                    # OpenRouter/OpenAI format: tool_call.function.name, tool_call.function.arguments
                    function_data = tool_call.get("function", {})
                    arguments = function_data.get("arguments", "{}")

                    # Parse arguments if string
                    if isinstance(arguments, str):
                        import json
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                    # Convert to Anthropic format
                    content_blocks.append({
                        "type": CONTENT_TYPE_TOOL_USE,
                        "id": tool_call.get("id", ""),
                        "name": function_data.get("name", ""),
                        "input": arguments
                    })

            # Extract usage info
            usage = response_data.get("usage", {})

            # Determine stop reason
            stop_reason = first_choice.get("finish_reason")
            if stop_reason == "tool_calls":
                stop_reason = CONTENT_TYPE_TOOL_USE


            opr_message_response = LLMResponse(
                content=content_blocks,
                stop_reason=stop_reason,
                usage=usage,
                model=response_data.get("model"),
            )

            logger.info(f"message response in converter: {opr_message_response} ")

            return opr_message_response

        except Exception as e:
            raise MessageFormatError(f"Failed to parse OpenRouter response: {e}") from e

    # ========================================================================
    # Message Construction Helpers
    # ========================================================================

    @staticmethod
    def create_user_message(content: Union[str, List[Dict], List[ContentBlock]]) -> Dict[str, Any]:
        """
        Create a user message in standardized format.

        Replaces duplicated logic in openrouter.py: add_user_message()

        Args:
            content: Message content (text or structured blocks)

        Returns:
            User message dictionary
        """
        return {
            "role": ROLE_USER,
            "content": MessageConverter._normalize_content(content),
        }

    @staticmethod
    def create_assistant_message(content: Union[str, List[Dict], LLMResponse]) -> Dict[str, Any]:
        """
        Create an assistant message in standardized format.

        Replaces duplicated logic in openrouter.py: add_assistant_message()

        Args:
            content: Message content (text, blocks, or LLMResponse)

        Returns:
            Assistant message dictionary
        """
        if isinstance(content, LLMResponse):
            normalized_content = content.content
        else:
            normalized_content = MessageConverter._normalize_content(content)

        return {
            "role": ROLE_ASSISTANT,
            "content": normalized_content,
        }

    @staticmethod
    def create_tool_result_message(tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a user message with tool results.

        Args:
            tool_results: List of tool execution results

        Returns:
            User message with tool results
        """
        tool_result_blocks = []
        for result in tool_results:
            tool_result_blocks.append(
                {
                    "type": CONTENT_TYPE_TOOL_RESULT,
                    "tool_use_id": result.get("tool_use_id", result.get("id", "")),
                    "content": result.get("content", ""),
                    "is_error": result.get("is_error", False),
                }
            )
        logger.info(f"tool_result_blocks: {tool_result_blocks}")

        return {"role": ROLE_USER, "content": tool_result_blocks}

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    @staticmethod
    def _normalize_content(
            content: Union[str, List[Dict], List[ContentBlock], LLMResponse, Any]
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Normalize content to a consistent format.

        Args:
            content: Content in various formats

        Returns:
            Normalized content (string or list of dicts)
        """
        # Handle string content
        if isinstance(content, str):
            return content

        # Handle LLMResponse
        if isinstance(content, LLMResponse):
            return content.content

        # Handle list of ContentBlock (Pydantic models)
        if isinstance(content, list):
            normalized = []
            for item in content:
                if isinstance(item, TextContent):
                    normalized.append({"type": CONTENT_TYPE_TEXT, "text": item.text})
                elif isinstance(item, ToolUseContent):
                    normalized.append(
                        {
                            "type": CONTENT_TYPE_TOOL_USE,
                            "id": item.id,
                            "name": item.name,
                            "input": item.input,
                        }
                    )
                elif isinstance(item, ToolResultContent):
                    normalized.append(
                        {
                            "type": CONTENT_TYPE_TOOL_RESULT,
                            "tool_use_id": item.tool_use_id,
                            "content": item.content,
                            "is_error": item.is_error,
                        }
                    )
                elif isinstance(item, dict):
                    normalized.append(item)
                else:
                    # Fallback to string
                    normalized.append({"type": CONTENT_TYPE_TEXT, "text": str(item)})

            return normalized if normalized else ""

        # Fallback to string conversion
        return str(content)

    # ========================================================================
    # Validation
    # ========================================================================

    @staticmethod
    def validate_message(message: Dict[str, Any]) -> bool:
        """
        Validate message structure.

        Args:
            message: Message to validate

        Returns:
            True if valid

        Raises:
            MessageFormatError: If message is invalid
        """
        if not isinstance(message, dict):
            raise MessageFormatError("Message must be a dictionary")

        if "role" not in message:
            raise MessageFormatError("Message must have a 'role' field")

        if message["role"] not in [ROLE_USER, ROLE_ASSISTANT, "system"]:
            raise MessageFormatError(f"Invalid role: {message['role']}")

        if "content" not in message:
            raise MessageFormatError("Message must have a 'content' field")

        return True
"""
Data models for LLM communication.

This module defines Pydantic models for type-safe LLM interactions.
"""
import logging
import sys
from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # MCP requires stdout only for JSONRPC messages
)
logger = logging.getLogger(__name__)

# ============================================================================
# Content Models
# ============================================================================


class TextContent(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str


class ToolUseContent(BaseModel):
    """Tool use content block."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    """Tool result content block."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]]]
    is_error: bool = False


ContentBlock = Union[TextContent, ToolUseContent, ToolResultContent]


# ============================================================================
# Message Models
# ============================================================================


class Message(BaseModel):
    """Unified message model."""

    role: Literal["user", "assistant", "system"]
    content: Union[str, List[ContentBlock]]


class UserMessage(Message):
    """User message."""

    role: Literal["user"] = "user"


class AssistantMessage(Message):
    """Assistant message."""

    role: Literal["assistant"] = "assistant"


class SystemMessage(Message):
    """System message."""

    role: Literal["system"] = "system"


# ============================================================================
# Tool Models
# ============================================================================


class ToolSchema(BaseModel):
    """Tool schema definition."""

    name: str
    description: str
    input_schema: Dict[str, Any]


class ToolCall(BaseModel):
    """Tool call from LLM."""

    id: str
    name: str
    input: Dict[str, Any]


class ToolResult(BaseModel):
    """Result of tool execution."""

    tool_use_id: str
    content: Union[str, Dict[str, Any]]
    is_error: bool = False


# ============================================================================
# LLM Response Models
# ============================================================================


class LLMResponse(BaseModel):
    """Unified LLM response model."""

    content: List[ContentBlock]
    stop_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None

    def get_text(self) -> str:
        """Extract all text content from response."""
        texts = []
        for block in self.content:
            if isinstance(block, TextContent):
                texts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return " ".join(texts).strip()

    def get_tool_calls(self) -> List[ToolCall]:
        """Extract all tool calls from response."""
        tool_calls = []

        logger.info(f"content: {self.content}")
        logger.info(f"stop_reason: {self.stop_reason}")

        # Caso 1: Tool calls nel content (formato Anthropic standard)
        for block in self.content:
            if isinstance(block, ToolUseContent):
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )
            elif isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        input=block.get("input", {}),
                    )
                )

        # Caso 2: Se stop_reason è 'tool_use' ma non abbiamo trovato tool calls
        # potrebbe essere in un campo separato (controlla self.__dict__)
        if not tool_calls and self.stop_reason == "tool_use":
            logger.warning(
                f"stop_reason is 'tool_use' but no tool calls found in content. "
                f"Response attributes: {list(self.__dict__.keys())}"
            )

            # Prova a cercare in attributi alternativi
            if hasattr(self, 'tool_calls'):
                logger.info(f"Found tool_calls attribute: {self.tool_calls}")
                # Converti dal formato trovato
                for tc in self.tool_calls:
                    if isinstance(tc, dict):
                        tool_calls.append(
                            ToolCall(
                                id=tc.get("id", ""),
                                name=tc.get("function", {}).get("name", ""),
                                input=tc.get("function", {}).get("arguments", {}),
                            )
                        )

        logger.info(f"Extracted {len(tool_calls)} tool calls")
        return tool_calls

    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.get_tool_calls()) > 0


# ============================================================================
# Chat Request Models
# ============================================================================


class LLMChatRequest(BaseModel):
    """Chat request parameters."""

    messages: List[Message]
    tools: Optional[List[ToolSchema]] = None
    max_tokens: int = Field(default=10000, ge=1, le=100000)
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop: Optional[Union[str, List[str]]] = None


# ============================================================================
# Utility functions
# ============================================================================


def content_to_text(content: Union[str, List[ContentBlock], List[Dict]]) -> str:
    """
    Extract text from various content formats.

    Args:
        content: Content in various formats (str, list of blocks, etc.)

    Returns:
        Extracted text as string
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, TextContent):
                texts.append(item.text)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif "text" in item:
                    texts.append(item["text"])
        return " ".join(texts).strip()

    return str(content)
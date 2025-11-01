"""
Domain models for Chat Service.

These models represent the core business entities for chat functionality,
independent of infrastructure concerns (API, CLI, etc.).
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Conversation Models
# ============================================================================


class ConversationMessage(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationState(BaseModel):
    """
    Represents the state of an ongoing conversation.

    This includes the message history, current iteration count,
    and any context needed to continue the conversation.
    """

    messages: List[ConversationMessage] = Field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    context: Dict[str, Any] = Field(default_factory=dict)
    is_complete: bool = False

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a message to the conversation."""
        message = ConversationMessage(
            role=role, content=content, metadata=metadata or {}
        )
        self.messages.append(message)

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration_count += 1
        if self.iteration_count >= self.max_iterations:
            self.is_complete = True

    def get_messages_for_llm(self) -> List[Dict[str, Any]]:
        """
        Convert conversation messages to format suitable for LLM.

        Returns:
            List of message dictionaries with role and content
        """
        return [
            {"role": msg.role, "content": msg.content} for msg in self.messages
        ]


# ============================================================================
# Request/Response Models
# ============================================================================


class UserChatRequest(BaseModel):
    """Request to process a chat query."""

    query: str = Field(..., min_length=1, description="User query to process")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Maximum conversation iterations")
    temperature: float = Field(default=0.4, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=10000, ge=1, le=100000, description="Maximum tokens to generate")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class ChatResponse(BaseModel):
    """Response from chat service."""

    response: str = Field(..., description="Final response text")
    iterations_used: int = Field(..., description="Number of iterations used")
    tools_called: int = Field(default=0, description="Number of tools executed")
    conversation_state: Optional[ConversationState] = Field(
        default=None, description="Final conversation state (if needed)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# Resource Models
# ============================================================================


class Resource(BaseModel):
    """Represents a resource (document, file, etc.) accessible via MCP."""

    id: str
    name: str
    uri: str
    type: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResourceContent(BaseModel):
    """Content of a loaded resource."""

    resource_id: str
    content: str
    content_type: str
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Command Models (for CLI-style interactions)
# ============================================================================


class Command(BaseModel):
    """Represents a parsed command (e.g., /summarize document_id)."""

    command_name: str
    arguments: List[str] = Field(default_factory=list)
    raw_input: str

    @classmethod
    def parse(cls, input_text: str) -> Optional["Command"]:
        """
        Parse a command from input text.

        Args:
            input_text: Raw input text starting with /

        Returns:
            Command object if valid, None otherwise
        """
        if not input_text.startswith("/"):
            return None

        parts = input_text[1:].split()
        if not parts:
            return None

        return cls(
            command_name=parts[0],
            arguments=parts[1:] if len(parts) > 1 else [],
            raw_input=input_text,
        )


class ResourceReference(BaseModel):
    """Represents a reference to a resource (e.g., @document_id)."""

    resource_id: str
    raw_reference: str

    @classmethod
    def parse_from_query(cls, query: str) -> List["ResourceReference"]:
        """
        Extract all resource references from a query.

        Args:
            query: Query text potentially containing @resource_id references

        Returns:
            List of ResourceReference objects
        """
        import re

        # Find all words starting with @
        pattern = r"@(\S+)"
        matches = re.findall(pattern, query)

        return [
            cls(resource_id=match, raw_reference=f"@{match}") for match in matches
        ]


# ============================================================================
# Tool Execution Models
# ============================================================================


class ToolCallRequest(BaseModel):
    """Request to execute a tool."""

    tool_id: str
    tool_name: str
    input: Dict[str, Any]


class ToolCallResult(BaseModel):
    """Result of a tool execution."""

    tool_use_id: str
    content: str
    is_error: bool = False
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
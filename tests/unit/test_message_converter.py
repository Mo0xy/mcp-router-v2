"""
Unit tests for MessageConverter.

These tests demonstrate that the refactored MessageConverter correctly
handles all the scenarios that were previously scattered across the codebase.
"""

import pytest
from src.infrastructure.llm.message_converter import MessageConverter
from src.infrastructure.llm.models import (
    LLMResponse,
    TextContent,
    ToolUseContent,
    ToolResultContent,
)
from src.shared.exceptions import MessageFormatError


class TestExtractTextFromContent:
    """Test text extraction from various content formats."""

    def test_extract_from_string(self):
        """Should extract text from plain string."""
        result = MessageConverter.extract_text_from_content("Hello, world!")
        assert result == "Hello, world!"

    def test_extract_from_text_blocks(self):
        """Should extract and concatenate text from multiple text blocks."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ]
        result = MessageConverter.extract_text_from_content(content)
        assert result == "Hello World"

    def test_extract_from_mixed_blocks(self):
        """Should extract only text blocks, ignoring other types."""
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "name": "calculator", "input": {}},
            {"type": "text", "text": "World"},
        ]
        result = MessageConverter.extract_text_from_content(content)
        assert result == "Hello World"

    def test_extract_from_empty_list(self):
        """Should return empty string for empty list."""
        result = MessageConverter.extract_text_from_content([])
        assert result == ""

    def test_extract_from_pydantic_models(self):
        """Should extract text from Pydantic ContentBlock models."""
        content = [
            TextContent(text="Hello"),
            TextContent(text="World"),
        ]
        result = MessageConverter.extract_text_from_content(content)
        assert result == "Hello World"


class TestOpenRouterConversion:
    """Test conversion to/from OpenRouter format."""

    def test_to_openrouter_message_from_dict(self):
        """Should convert dictionary message to OpenRouter format."""
        message = {"role": "user", "content": "Hello"}
        result = MessageConverter.to_openrouter_message(message)

        assert result["role"] == "user"
        assert result["content"] == "Hello"

    def test_to_openrouter_message_with_blocks(self):
        """Should convert message with content blocks."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ],
        }
        result = MessageConverter.to_openrouter_message(message)

        assert result["role"] == "assistant"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 2

    def test_to_openrouter_messages_batch(self):
        """Should convert multiple messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = MessageConverter.to_openrouter_messages(messages)

        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"

    def test_from_openrouter_response_simple(self):
        """Should parse simple OpenRouter response."""
        response_data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "test-model",
        }

        result = MessageConverter.from_openrouter_response(response_data)

        assert isinstance(result, LLMResponse)
        assert result.get_text() == "Hello!"
        assert result.stop_reason == "stop"
        assert result.model == "test-model"

    def test_from_openrouter_response_with_tools(self):
        """Should parse OpenRouter response with tool calls."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Let me calculate that"},
                            {
                                "type": "tool_use",
                                "id": "tool_123",
                                "name": "calculator",
                                "input": {"operation": "add", "a": 5, "b": 3},
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }

        result = MessageConverter.from_openrouter_response(response_data)

        assert result.has_tool_calls()
        tool_calls = result.get_tool_calls()
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "calculator"
        assert tool_calls[0].input["operation"] == "add"

    def test_from_openrouter_response_invalid(self):
        """Should raise error for invalid response."""
        response_data = {"choices": []}  # Empty choices

        with pytest.raises(MessageFormatError):
            MessageConverter.from_openrouter_response(response_data)


class TestMessageConstruction:
    """Test message construction helpers."""

    def test_create_user_message_string(self):
        """Should create user message from string."""
        result = MessageConverter.create_user_message("Hello")

        assert result["role"] == "user"
        assert result["content"] == "Hello"

    def test_create_user_message_blocks(self):
        """Should create user message from content blocks."""
        content = [{"type": "text", "text": "Hello"}]
        result = MessageConverter.create_user_message(content)

        assert result["role"] == "user"
        assert isinstance(result["content"], list)

    def test_create_assistant_message_string(self):
        """Should create assistant message from string."""
        result = MessageConverter.create_assistant_message("Hello")

        assert result["role"] == "assistant"
        assert result["content"] == "Hello"

    def test_create_assistant_message_from_llm_response(self):
        """Should create assistant message from LLMResponse."""
        llm_response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}], stop_reason="stop"
        )

        result = MessageConverter.create_assistant_message(llm_response)

        assert result["role"] == "assistant"
        assert isinstance(result["content"], list)

    def test_create_tool_result_message(self):
        """Should create tool result message."""
        tool_results = [
            {
                "tool_use_id": "tool_123",
                "content": "The answer is 42",
                "is_error": False,
            }
        ]

        result = MessageConverter.create_tool_result_message(tool_results)

        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "tool_result"
        assert result["content"][0]["tool_use_id"] == "tool_123"


class TestValidation:
    """Test message validation."""

    def test_validate_valid_message(self):
        """Should validate correct message."""
        message = {"role": "user", "content": "Hello"}
        assert MessageConverter.validate_message(message) is True

    def test_validate_missing_role(self):
        """Should raise error for missing role."""
        message = {"content": "Hello"}
        with pytest.raises(MessageFormatError, match="must have a 'role' field"):
            MessageConverter.validate_message(message)

    def test_validate_missing_content(self):
        """Should raise error for missing content."""
        message = {"role": "user"}
        with pytest.raises(MessageFormatError, match="must have a 'content' field"):
            MessageConverter.validate_message(message)

    def test_validate_invalid_role(self):
        """Should raise error for invalid role."""
        message = {"role": "invalid", "content": "Hello"}
        with pytest.raises(MessageFormatError, match="Invalid role"):
            MessageConverter.validate_message(message)

    def test_validate_non_dict(self):
        """Should raise error for non-dictionary input."""
        with pytest.raises(MessageFormatError, match="must be a dictionary"):
            MessageConverter.validate_message("not a dict")


class TestToolExtraction:
    """Test tool call extraction."""

    def test_extract_tool_calls(self):
        """Should extract tool calls from content."""
        content = [
            {"type": "text", "text": "Let me help"},
            {
                "type": "tool_use",
                "id": "tool_1",
                "name": "calculator",
                "input": {"a": 5, "b": 3},
            },
            {
                "type": "tool_use",
                "id": "tool_2",
                "name": "search",
                "input": {"query": "test"},
            },
        ]

        result = MessageConverter.extract_tool_calls(content)

        assert len(result) == 2
        assert result[0]["name"] == "calculator"
        assert result[1]["name"] == "search"

    def test_extract_no_tool_calls(self):
        """Should return empty list if no tool calls."""
        content = [{"type": "text", "text": "Just text"}]
        result = MessageConverter.extract_tool_calls(content)
        assert result == []


# ============================================================================
# Integration-style tests showing real-world usage
# ============================================================================


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_complete_conversation_flow(self):
        """Test a complete conversation with tool use."""
        # 1. User asks a question
        user_msg = MessageConverter.create_user_message("What is 5 + 3?")
        assert user_msg["role"] == "user"

        # 2. Assistant responds with tool use
        assistant_response = LLMResponse(
            content=[
                {"type": "text", "text": "Let me calculate that"},
                {
                    "type": "tool_use",
                    "id": "calc_1",
                    "name": "calculator",
                    "input": {"operation": "add", "a": 5, "b": 3},
                },
            ],
            stop_reason="tool_use",
        )

        assistant_msg = MessageConverter.create_assistant_message(assistant_response)
        assert assistant_msg["role"] == "assistant"
        assert len(assistant_msg["content"]) == 2

        # 3. Tool executes and returns result
        tool_result_msg = MessageConverter.create_tool_result_message(
            [{"tool_use_id": "calc_1", "content": "8", "is_error": False}]
        )
        assert tool_result_msg["role"] == "user"

        # 4. Convert all to OpenRouter format
        all_messages = [user_msg, assistant_msg, tool_result_msg]
        openrouter_messages = MessageConverter.to_openrouter_messages(all_messages)

        assert len(openrouter_messages) == 3
        assert all(isinstance(msg, dict) for msg in openrouter_messages)
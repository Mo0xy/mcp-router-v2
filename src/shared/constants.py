"""
Global constants for MCP Router.

This module contains all constant values used across the application.
"""

from typing import Final

# ============================================================================
# API Configuration
# ============================================================================

API_VERSION: Final[str] = "1.0.0"
API_TITLE: Final[str] = "MCP Router API"
API_DESCRIPTION: Final[str] = """
MCP Router is a FastAPI application that implements the Model Context Protocol (MCP),
standardizing interactions between applications and AI models via OpenRouter.
"""

# ============================================================================
# Default Values
# ============================================================================

DEFAULT_MODEL: Final[str] = "deepseek/deepseek-chat-v3.1:free"
DEFAULT_TIMEOUT: Final[float] = 120.0
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_MAX_TOKENS: Final[int] = 10000
DEFAULT_TEMPERATURE: Final[float] = 0.4

# ============================================================================
# Message Roles
# ============================================================================

ROLE_USER: Final[str] = "user"
ROLE_ASSISTANT: Final[str] = "assistant"
ROLE_SYSTEM: Final[str] = "system"

# ============================================================================
# Content Types
# ============================================================================

CONTENT_TYPE_TEXT: Final[str] = "text"
CONTENT_TYPE_TOOL_USE: Final[str] = "tool_use"
CONTENT_TYPE_TOOL_RESULT: Final[str] = "tool_result"

# ============================================================================
# Stop Reasons
# ============================================================================

STOP_REASON_END_TURN: Final[str] = "end_turn"
STOP_REASON_TOOL_USE: Final[str] = "tool_use"
STOP_REASON_MAX_TOKENS: Final[str] = "max_tokens"
STOP_REASON_STOP_SEQUENCE: Final[str] = "stop_sequence"

# ============================================================================
# HTTP Configuration
# ============================================================================

OPENROUTER_BASE_URL: Final[str] = "https://openrouter.ai/api/v1"
HTTP_TIMEOUT: Final[float] = 120.0

# ============================================================================
# Retry Configuration
# ============================================================================

RETRY_BACKOFF_FACTOR: Final[float] = 2.0
RETRY_MAX_DELAY: Final[float] = 60.0
RETRY_STATUS_CODES: Final[tuple] = (429, 500, 502, 503, 504)

# ============================================================================
# Logging
# ============================================================================

LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# Resource Prefixes
# ============================================================================

RESOURCE_PREFIX: Final[str] = "@"
COMMAND_PREFIX: Final[str] = "/"

# ============================================================================
# Limits
# ============================================================================

MAX_CONVERSATION_ITERATIONS: Final[int] = 5
MAX_TOOL_CALLS_PER_ITERATION: Final[int] = 10
MAX_MESSAGE_LENGTH: Final[int] = 100000
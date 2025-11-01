"""
Custom exceptions for MCP Router.

This module defines all custom exceptions used throughout the application,
providing a clear hierarchy and error handling strategy.
"""

from typing import Optional, Dict, Any


class MCPRouterException(Exception):
    """Base exception for all MCP Router errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ============================================================================
# Infrastructure Layer Exceptions
# ============================================================================


class LLMProviderError(MCPRouterException):
    """Raised when LLM provider (e.g., OpenRouter) returns an error."""

    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when LLM request times out."""

    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when LLM rate limit is exceeded."""

    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when LLM authentication fails."""

    pass


# ============================================================================
# MCP Layer Exceptions
# ============================================================================


class MCPConnectionError(MCPRouterException):
    """Raised when MCP client connection fails."""

    pass


class MCPServerError(MCPRouterException):
    """Raised when MCP server encounters an error."""

    pass


class MCPTimeoutError(MCPConnectionError):
    """Raised when MCP operation times out."""

    pass


# ============================================================================
# Tool Execution Exceptions
# ============================================================================


class ToolExecutionError(MCPRouterException):
    """Raised when tool execution fails."""

    pass


class ToolNotFoundException(ToolExecutionError):
    """Raised when requested tool is not found."""

    pass


class ToolValidationError(ToolExecutionError):
    """Raised when tool input validation fails."""

    pass


# ============================================================================
# Resource Exceptions
# ============================================================================


class ResourceError(MCPRouterException):
    """Raised when resource operation fails."""

    pass


class ResourceNotFoundException(ResourceError):
    """Raised when requested resource is not found."""

    pass


class ResourceAccessError(ResourceError):
    """Raised when resource access is denied or fails."""

    pass


# ============================================================================
# Configuration Exceptions
# ============================================================================


class ConfigurationError(MCPRouterException):
    """Raised when configuration is invalid or missing."""

    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when required environment variable is missing."""

    def __init__(self, var_name: str):
        super().__init__(
            f"Missing required environment variable: {var_name}",
            details={"variable": var_name},
        )


# ============================================================================
# Validation Exceptions
# ============================================================================


class ValidationError(MCPRouterException):
    """Raised when input validation fails."""

    pass


class MessageFormatError(ValidationError):
    """Raised when message format is invalid."""

    pass


class DatabaseError(Exception):
    """Raised when a database operation fails."""

    pass

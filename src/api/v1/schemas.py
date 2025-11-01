"""
API request/response schemas.

These Pydantic models define the API contract for HTTP endpoints,
separate from domain models to maintain clean architecture.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ============================================================================
# Health Check Schemas
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status (healthy/unhealthy)")
    version: str = Field(..., description="Application version")
    timestamp: str = Field(..., description="Current timestamp")
    mcp_clients: Dict[str, bool] = Field(
        default_factory=dict, description="MCP client connection status"
    )


# ============================================================================
# Chat Schemas
# ============================================================================


class ChatRequest(BaseModel):
    """
    Chat request from API client.

    This is the HTTP API schema, separate from domain ChatRequest.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="User prompt/query",
        examples=["What is the capital of France?"]
    )
    max_iterations: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Maximum conversation iterations (uses default if not specified)"
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="LLM temperature (uses default if not specified)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=100000,
        description="Maximum tokens to generate (uses default if not specified)"
    )
    include_metadata: bool = Field(
        default=False,
        description="Include additional metadata in response"
    )


class ChatResponse(BaseModel):
    """Chat response to API client."""

    response: str = Field(..., description="Generated response text")
    iterations: int = Field(..., description="Number of iterations used")
    tools_called: int = Field(default=0, description="Number of tools executed")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata (only if requested)"
    )


# ============================================================================
# Error Schemas
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: Optional[str] = Field(default=None, description="Field name (for validation errors)")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(default=None, description="Error code")


class ErrorResponse(BaseModel):
    """Error response format."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[List[ErrorDetail]] = Field(
        default=None, description="Detailed error information"
    )
    request_id: Optional[str] = Field(
        default=None, description="Request ID for tracking"
    )


# ============================================================================
# Tools Schemas
# ============================================================================


class ToolSchema(BaseModel):
    """Tool information schema."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: Dict[str, Any] = Field(..., description="Tool input schema")


class ListToolsResponse(BaseModel):
    """Response for listing available tools."""

    tools: List[ToolSchema] = Field(..., description="List of available tools")
    count: int = Field(..., description="Total number of tools")


# ============================================================================
# Resources Schemas
# ============================================================================


class ResourceSchema(BaseModel):
    """Resource information schema."""

    id: str = Field(..., description="Resource identifier")
    name: str = Field(..., description="Resource name")
    uri: str = Field(..., description="Resource URI")
    type: str = Field(..., description="Resource type")
    description: Optional[str] = Field(default=None, description="Resource description")


class ListResourcesResponse(BaseModel):
    """Response for listing available resources."""

    resources: List[ResourceSchema] = Field(..., description="List of available resources")
    count: int = Field(..., description="Total number of resources")


# ============================================================================
# System Info Schemas
# ============================================================================


class SystemInfoResponse(BaseModel):
    """System information response."""

    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    model: str = Field(..., description="Current LLM model")
    mcp_clients: List[str] = Field(..., description="List of MCP client names")
    uptime_seconds: float = Field(..., description="Application uptime in seconds")
"""
API routes for MCP Router.

This module defines all HTTP endpoints with proper dependency injection,
error handling, and OpenAPI documentation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
import time
import logging

from src.api.v1.schemas import (
    HealthResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ListToolsResponse,
    ListResourcesResponse,
    SystemInfoResponse,
    ToolSchema,
    ResourceSchema,
)
from src.api.v1.dependencies import (
    get_chat_service,
    get_tool_manager,
    get_mcp_clients,
    get_app_settings,
)
from src.domain.chat.service import ChatService
from src.domain.tools.manager import ToolManager
from src.domain.mcp.client import MCPClient
from src.config.settings import Settings
from src.shared.exceptions import (
    MCPRouterException,
    ToolExecutionError,
    LLMProviderError,
)
from src.domain.chat.models import UserChatRequest as DomainChatRequest

logger = logging.getLogger(__name__)

# Application start time for uptime tracking
_app_start_time = time.time()

# Create router
router = APIRouter()


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Check if the API is running and MCP clients are connected",
)
async def health_check(
        tool_manager: ToolManager = Depends(get_tool_manager),
        settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    """
    Perform health check.

    Returns application status and MCP client connectivity.
    """
    try:
        # Test MCP client connections
        mcp_status = await tool_manager.test_connections()

        # Determine overall health
        all_healthy = all(mcp_status.values())
        status_str = "healthy" if all_healthy else "degraded"

        return HealthResponse(
            status=status_str,
            version=settings.app_version,
            timestamp=datetime.utcnow().isoformat(),
            mcp_clients=mcp_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            version=settings.app_version,
            timestamp=datetime.utcnow().isoformat(),
            mcp_clients={},
        )


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    tags=["System"],
    summary="System information",
    description="Get detailed system information",
)
async def system_info(
        mcp_clients: dict[str, MCPClient] = Depends(get_mcp_clients),
        settings: Settings = Depends(get_app_settings),
) -> SystemInfoResponse:
    """Get system information."""
    uptime = time.time() - _app_start_time

    return SystemInfoResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        model=settings.model,
        mcp_clients=list(mcp_clients.keys()),
        uptime_seconds=uptime,
    )


# ============================================================================
# Chat Endpoints
# ============================================================================


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["Chat"],
    summary="Chat with AI",
    description="Send a chat query and get a response with optional tool execution",
)
async def chat(
        request: ChatRequest,
        chat_service: ChatService = Depends(get_chat_service),
        settings: Settings = Depends(get_app_settings),
) -> ChatResponse:
    """
    Process a chat query.

    The service will:
    1. Process the user query
    2. Call LLM with available tools
    3. Execute any requested tools
    4. Return final response
    """
    try:
        logger.info(f"Chat request received: {request.prompt[:50]}...")

        # Build domain request
        domain_request = DomainChatRequest(
            query=request.prompt,
            max_iterations=request.max_iterations or settings.max_iterations,
            temperature=request.temperature or settings.default_temperature,
            max_tokens=request.max_tokens or settings.default_max_tokens,
        )

        # Process via chat service
        domain_response = await chat_service.process_query(domain_request)

        # Build API response
        response = ChatResponse(
            response=domain_response.response,
            iterations=domain_response.iterations_used,
            tools_called=domain_response.tools_called,
            metadata=domain_response.metadata if request.include_metadata else None,
        )

        logger.info(
            f"Chat completed: {domain_response.iterations_used} iterations, "
            f"{domain_response.tools_called} tools"
        )

        return response

    except LLMProviderError as e:
        logger.error(f"LLM provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {e.message}",
        )
    except ToolExecutionError as e:
        logger.error(f"Tool execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {e.message}",
        )
    except MCPRouterException as e:
        logger.error(f"MCP Router error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


# ============================================================================
# Tools Endpoints
# ============================================================================


@router.get(
    "/tools",
    response_model=ListToolsResponse,
    tags=["Tools"],
    summary="List available tools",
    description="Get all tools available from MCP servers",
)
async def list_tools(
        tool_manager: ToolManager = Depends(get_tool_manager),
) -> ListToolsResponse:
    """List all available tools."""
    try:
        tools = await tool_manager.get_all_tools()

        tool_schemas = [
            ToolSchema(
                name=tool["name"],
                description=tool["description"],
                input_schema=tool["input_schema"],
            )
            for tool in tools
        ]

        return ListToolsResponse(tools=tool_schemas, count=len(tool_schemas))

    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tools",
        )


# ============================================================================
# Resources Endpoints
# ============================================================================


@router.get(
    "/resources",
    response_model=ListResourcesResponse,
    tags=["Resources"],
    summary="List available resources",
    description="Get all resources available from MCP servers",
)
async def list_resources(
        mcp_clients: dict[str, MCPClient] = Depends(get_mcp_clients),
) -> ListResourcesResponse:
    """List all available resources."""
    try:
        all_resources = []

        for client_name, client in mcp_clients.items():
            try:
                resources = await client.list_resources()
                for resource in resources:
                    all_resources.append(
                        ResourceSchema(
                            id=resource.get("id", ""),
                            name=resource.get("name", ""),
                            uri=resource.get("uri", ""),
                            type=resource.get("type", ""),
                            description=resource.get("description"),
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to list resources from {client_name}: {e}")
                continue

        return ListResourcesResponse(resources=all_resources, count=len(all_resources))

    except Exception as e:
        logger.error(f"Error listing resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list resources",
        )


# ============================================================================
# Legacy Endpoint (for backwards compatibility)
# ============================================================================


@router.post(
    "/chat_alternative",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Alternative chat endpoint",
    description="Alternative chat endpoint (same as /chat)",
    deprecated=True,
)
async def chat_alternative(
        request: ChatRequest,
        chat_service: ChatService = Depends(get_chat_service),
        settings: Settings = Depends(get_app_settings),
) -> ChatResponse:
    """
    Alternative chat endpoint (deprecated).

    Use /chat instead. This endpoint is maintained for backwards compatibility.
    """
    return await chat(request, chat_service, settings)


# ============================================================================
# Query Parameter Style Endpoint (for backwards compatibility)
# ============================================================================


@router.get(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Chat with query parameter",
    description="Chat endpoint accepting prompt as query parameter",
    deprecated=True,
)
async def chat_query_param(
        prompt: str,
        chat_service: ChatService = Depends(get_chat_service),
        settings: Settings = Depends(get_app_settings),
) -> ChatResponse:
    """
    Chat endpoint with query parameter (deprecated).

    Use POST /chat with JSON body instead.
    """
    request = ChatRequest(prompt=prompt)
    return await chat(request, chat_service, settings)
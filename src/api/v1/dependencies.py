"""
FastAPI dependency injection providers.

This module provides all dependencies needed by API endpoints,
following dependency injection principles for testability and flexibility.
"""

from typing import Dict, AsyncGenerator
from fastapi import Depends
from contextlib import asynccontextmanager

from src.config.settings import Settings, get_settings
from src.infrastructure.llm.openrouter import OpenRouterClient
from src.infrastructure.llm.base import LLMProvider
from src.domain.mcp.client import MCPClient
from src.domain.tools.manager import ToolManager
from src.domain.chat.service import ChatService
from src.shared.exceptions import ConfigurationError

import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Settings Dependency
# ============================================================================


def get_app_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance (cached)
    """
    return get_settings()


# ============================================================================
# LLM Provider Dependencies
# ============================================================================


def get_llm_provider(settings: Settings = Depends(get_app_settings)) -> LLMProvider:
    """
    Get LLM provider instance (OpenRouter).

    Args:
        settings: Application settings

    Returns:
        LLMProvider instance

    Raises:
        ConfigurationError: If LLM provider cannot be initialized
    """
    try:
        provider = OpenRouterClient(
            model=settings.model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_timeout=settings.default_timeout,
        )
        logger.debug(f"LLM Provider initialized: {settings.model}")
        return provider
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        raise ConfigurationError(f"LLM provider initialization failed: {e}")


# ============================================================================
# MCP Client Dependencies
# ============================================================================


# Global MCP clients cache (initialized at startup)
_mcp_clients: Dict[str, MCPClient] = {}


async def initialize_mcp_clients(settings: Settings) -> Dict[str, MCPClient]:
    """
    Initialize MCP clients at application startup.

    This should be called in the FastAPI lifespan event.

    Args:
        settings: Application settings

    Returns:
        Dictionary of initialized MCP clients
    """
    global _mcp_clients

    if _mcp_clients:
        logger.warning("MCP clients already initialized")
        return _mcp_clients

    logger.info("Initializing MCP clients...")

    try:
        # Initialize LLM provider for MCP sampling
        llm_provider = OpenRouterClient(
            model=settings.model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_timeout=settings.default_timeout,
        )

        # Initialize MCP client
        mcp_client = MCPClient(
            command=settings.mcp_server_command,
            args=settings.mcp_server_args_list,
            openrouter_client=llm_provider,
        )

        await mcp_client.connect()

        _mcp_clients["default"] = mcp_client

        logger.info(f"MCP clients initialized: {list(_mcp_clients.keys())}")
        return _mcp_clients

    except Exception as e:
        logger.error(f"Failed to initialize MCP clients: {e}")
        raise ConfigurationError(f"MCP client initialization failed: {e}")


async def cleanup_mcp_clients() -> None:
    """
    Cleanup MCP clients at application shutdown.

    This should be called in the FastAPI lifespan event.
    """
    global _mcp_clients

    logger.info("Cleaning up MCP clients...")

    for name, client in _mcp_clients.items():
        try:
            await client.cleanup()
            logger.info(f"Cleaned up MCP client: {name}")
        except Exception as e:
            logger.warning(f"Error cleaning up MCP client {name}: {e}")

    _mcp_clients.clear()
    logger.info("MCP clients cleanup completed")


def get_mcp_clients() -> Dict[str, MCPClient]:
    """
    Get initialized MCP clients.

    Returns:
        Dictionary of MCP clients

    Raises:
        ConfigurationError: If MCP clients not initialized
    """
    if not _mcp_clients:
        raise ConfigurationError(
            "MCP clients not initialized. Ensure initialize_mcp_clients() "
            "was called at startup."
        )
    return _mcp_clients


# ============================================================================
# Tool Manager Dependency
# ============================================================================


def get_tool_manager(
        mcp_clients: Dict[str, MCPClient] = Depends(get_mcp_clients)
) -> ToolManager:
    """
    Get tool manager instance.

    Args:
        mcp_clients: Dictionary of MCP clients

    Returns:
        ToolManager instance
    """
    return ToolManager(clients=mcp_clients)


# ============================================================================
# Chat Service Dependency
# ============================================================================


def get_chat_service(
        llm_provider: LLMProvider = Depends(get_llm_provider),
        tool_manager: ToolManager = Depends(get_tool_manager),
        mcp_clients: Dict[str, MCPClient] = Depends(get_mcp_clients),
        settings: Settings = Depends(get_app_settings),
) -> ChatService:
    """
    Get chat service instance with all dependencies.

    Args:
        llm_provider: LLM provider instance
        tool_manager: Tool manager instance
        mcp_clients: Dictionary of MCP clients
        settings: Application settings

    Returns:
        ChatService instance
    """
    return ChatService(
        llm_provider=llm_provider,
        tool_manager=tool_manager,
        mcp_clients=mcp_clients,
        default_max_iterations=settings.max_iterations,
        default_temperature=settings.default_temperature,
        default_max_tokens=settings.default_max_tokens,
    )


# ============================================================================
# Lifespan Context Manager
# ============================================================================


@asynccontextmanager
async def lifespan_manager(settings: Settings) -> AsyncGenerator[None, None]:
    """
    Manage application lifespan (startup/shutdown).

    This context manager handles:
    - MCP client initialization at startup
    - MCP client cleanup at shutdown

    Args:
        settings: Application settings

    Yields:
        None
    """
    # Startup
    logger.info("Application startup: Initializing resources...")
    try:
        await initialize_mcp_clients(settings)
        logger.info("✓ Application startup completed")
        yield
    finally:
        # Shutdown
        logger.info("Application shutdown: Cleaning up resources...")
        await cleanup_mcp_clients()
        logger.info("✓ Application shutdown completed")
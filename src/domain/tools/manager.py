"""
Tool Manager - Coordinates tool discovery and execution.

This is a lightweight coordinator that manages the ToolExecutor and
provides a simple interface for the domain layer.

REFACTORING FROM V1:
- V1: ToolManager had all execution logic (100+ lines of static methods)
- V2: ToolManager is a lightweight coordinator, ToolExecutor does the work
- Separation of concerns: Manager = coordination, Executor = execution
"""

from typing import Dict, List, Any
from src.domain.tools.executor import ToolExecutor
from src.domain.mcp.protocols import MCPClientProtocol
import logging

logger = logging.getLogger(__name__)


class ToolManager:
    """
    Manages tool discovery and delegates execution to ToolExecutor.

    This class acts as a facade/coordinator for tool operations,
    providing a simpler interface to the rest of the application.
    """

    def __init__(self, clients: Dict[str, MCPClientProtocol]):
        """
        Initialize tool manager.

        Args:
            clients: Dictionary of MCP clients
        """
        self.clients = clients
        self.executor = ToolExecutor(clients)
        self._tools_cache: List[Dict[str, Any]] = []
        self._cache_valid = False

    # ========================================================================
    # Tool Discovery (with caching)
    # ========================================================================

    async def get_all_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get all available tools (with optional caching).

        Args:
            use_cache: Whether to use cached tools if available

        Returns:
            List of tool schemas
        """
        if use_cache and self._cache_valid and self._tools_cache:
            logger.debug(f"Using cached tools ({len(self._tools_cache)} tools)")
            return self._tools_cache

        logger.debug("Fetching tools from MCP clients")
        tools = await self.executor.get_available_tools()

        # Update cache
        self._tools_cache = tools
        self._cache_valid = True

        return tools

    def invalidate_cache(self) -> None:
        """Invalidate the tools cache."""
        self._cache_valid = False
        logger.debug("Tools cache invalidated")

    # ========================================================================
    # Tool Execution (delegates to executor)
    # ========================================================================

    async def execute_tool_calls(
            self, tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool calls to execute

        Returns:
            List of tool execution results
        """
        return await self.executor.execute_tools(tool_calls)

    async def execute_single_tool(
            self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single tool.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        return await self.executor.execute_tool(tool_name, tool_input)

    # ========================================================================
    # Health Check
    # ========================================================================

    async def test_connections(self) -> Dict[str, bool]:
        """
        Test connectivity of all MCP clients.

        Returns:
            Dictionary mapping client names to connection status
        """
        return await self.executor.test_connection()

    # ========================================================================
    # Configuration
    # ========================================================================

    def configure_tool_timeout(self, tool_name: str, timeout: float) -> None:
        """
        Configure timeout for a specific tool.

        Args:
            tool_name: Name of the tool
            timeout: Timeout in seconds
        """
        self.executor.set_tool_timeout(tool_name, timeout)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def tool_exists(self, tool_name: str) -> bool:
        """
        Check if a tool exists.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool exists
        """
        tools = await self.get_all_tools()
        return any(tool["name"] == tool_name for tool in tools)

    async def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """
        Get the schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema dictionary

        Raises:
            ValueError: If tool not found
        """
        tools = await self.get_all_tools()

        for tool in tools:
            if tool["name"] == tool_name:
                return tool

        raise ValueError(f"Tool '{tool_name}' not found")
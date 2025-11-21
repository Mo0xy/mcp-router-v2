"""
Tool Executor - Handles tool execution logic.

This module replaces the static ToolManager from V1 with a proper
class that supports dependency injection and is easier to test.

REFACTORING FROM V1:
- V1: Static methods in ToolManager (@classmethod everywhere)
- V2: Instance-based ToolExecutor with injected dependencies
- Better: Testable, mockable, follows SOLID principles
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from src.domain.mcp.protocols import MCPClientProtocol
from src.shared.exceptions import ToolExecutionError, ToolNotFoundException
from src.shared.constants import MAX_TOOL_CALLS_PER_ITERATION
import logging

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tools via MCP clients.

    This class manages tool discovery and execution across multiple
    MCP clients, handling timeouts, errors, and result formatting.
    """

    def __init__(
            self,
            clients: Dict[str, MCPClientProtocol],
            default_timeout: float = 25.0,
            max_concurrent_tools: int = MAX_TOOL_CALLS_PER_ITERATION,
    ):
        """
        Initialize tool executor.

        Args:
            clients: Dictionary of MCP clients keyed by name
            default_timeout: Default timeout for tool execution (seconds)
            max_concurrent_tools: Maximum number of concurrent tool executions
        """
        self.clients = clients
        self.default_timeout = default_timeout
        self.max_concurrent_tools = max_concurrent_tools

        # Tool timeout configuration (can be customized)
        self.tool_timeouts = {
            # Read tools - fast
            "read_doc": 10.0,
            "get_doc_content": 10.0,
            "list_docs": 10.0,
            "server_status": 10.0,
            # Edit tools - medium
            "edit_doc": 20.0,
            # Complex tools - long
            "duplicate_doc": 30.0,
            # Search/analysis tools - very long
            "search": 45.0,
            "analyze": 60.0,
            "generate_interview_questions": 120.0,
            "analyze_transcription": 180.0,
        }

    # ========================================================================
    # Tool Discovery
    # ========================================================================

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get all available tools from all MCP clients.

        Returns:
            List of tool schemas in OpenRouter format

        Raises:
            ToolExecutionError: If tool discovery fails
        """
        tools = []

        for client_name, client in self.clients.items():
            try:
                logger.debug(f"Getting tools from client: {client_name}")

                tool_models = await asyncio.wait_for(
                    client.list_tools(), timeout=10.0
                )

                for tool in tool_models:
                    tool_dict = {
                        "name": tool.name,
                        "description": tool.description or f"Tool {tool.name}",
                        "input_schema": tool.inputSchema or {
                            "type": "object",
                            "properties": {},
                        },
                    }
                    tools.append(tool_dict)
                    logger.debug(f"Added tool: {tool.name}")

            except asyncio.TimeoutError:
                logger.error(f"Timeout getting tools from {client_name}")
            except Exception as e:
                logger.error(f"Error getting tools from {client_name}: {e}")

        logger.info(f"Total tools available: {len(tools)}")
        return tools

    async def find_client_for_tool(self, tool_name: str) -> Optional[MCPClientProtocol]:
        """
        Find which MCP client provides a specific tool.

        Args:
            tool_name: Name of the tool to find

        Returns:
            MCPClientProtocol instance or None if not found
        """
        for client_name, client in self.clients.items():
            try:
                tools = await asyncio.wait_for(client.list_tools(), timeout=5.0)
                if any(tool.name == tool_name for tool in tools):
                    logger.debug(f"Found tool '{tool_name}' in client '{client_name}'")
                    return client
            except Exception as e:
                logger.warning(f"Could not check tools in {client_name}: {e}")
                continue

        return None

    # ========================================================================
    # Tool Execution
    # ========================================================================

    async def execute_tool(
            self,
            tool_name: str,
            tool_input: Dict[str, Any],
            tool_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            tool_id: Optional tool call ID for tracking

        Returns:
            Tool execution result in standardized format

        Raises:
            ToolNotFoundException: If tool is not found
            ToolExecutionError: If execution fails
        """
        logger.info(f"Executing tool: {tool_name}")

        # Find the client that has this tool
        client = await self.find_client_for_tool(tool_name)

        if not client:
            raise ToolNotFoundException(
                f"Tool '{tool_name}' not found",
                details={"tool_name": tool_name, "available_clients": list(self.clients.keys())},
            )

        # Get timeout for this tool
        timeout = self.tool_timeouts.get(tool_name, self.default_timeout)

        # Execute the tool
        try:
            start_time = time.time()

            result = await asyncio.wait_for(
                client.call_tool(tool_name, tool_input), timeout=timeout
            )

            execution_time = (time.time() - start_time) * 1000  # ms

            logger.info(f"Tool '{tool_name}' completed in {execution_time:.2f}ms")

            # Extract content from result
            if hasattr(result, "content") and result.content:
                content = result.content[0].text if result.content else ""
            else:
                content = str(result)

            return {
                "tool_use_id": tool_id or f"tool_{tool_name}",
                "type": "tool_result",
                "content": content,
                "is_error": False,
                "execution_time_ms": execution_time,
            }

        except asyncio.TimeoutError:
            error_msg = f"Tool '{tool_name}' timed out after {timeout} seconds"
            logger.error(error_msg)

            return {
                "tool_use_id": tool_id or f"tool_{tool_name}",
                "type": "tool_result",
                "content": json.dumps({"error": error_msg, "tool_name": tool_name}),
                "is_error": True,
            }

        except Exception as e:
            error_msg = f"Tool '{tool_name}' failed: {str(e)}"
            logger.error(error_msg)

            return {
                "tool_use_id": tool_id or f"tool_{tool_name}",
                "type": "tool_result",
                "content": json.dumps({"error": error_msg, "tool_name": tool_name}),
                "is_error": True,
            }

    async def execute_tools(
            self, tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tools sequentially.

        Args:
            tool_calls: List of tool calls with format:
                        [{"id": str, "name": str, "input": dict}, ...]

        Returns:
            List of tool execution results
        """
        if not tool_calls:
            return []

        # Limit number of tool calls
        if len(tool_calls) > self.max_concurrent_tools:
            logger.warning(
                f"Tool calls ({len(tool_calls)}) exceeds max ({self.max_concurrent_tools}). "
                f"Only executing first {self.max_concurrent_tools}."
            )
            tool_calls = tool_calls[: self.max_concurrent_tools]

        logger.info(f"Executing {len(tool_calls)} tool(s)")

        results = []

        for i, tool_call in enumerate(tool_calls):
            tool_id = tool_call.get("id", f"tool_{i}")
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})

            logger.debug(f"Tool {i+1}/{len(tool_calls)}: {tool_name} (ID: {tool_id})")

            result = await self.execute_tool(
                tool_name=tool_name, tool_input=tool_input, tool_id=tool_id
            )

            results.append(result)

            # Small pause between tools to avoid overload
            if i < len(tool_calls) - 1:
                await asyncio.sleep(0.1)

        logger.info(f"Completed execution of {len(results)} tool(s)")
        return results

    # ========================================================================
    # Health Check
    # ========================================================================

    async def test_connection(self) -> Dict[str, bool]:
        """
        Test connectivity of all MCP clients.

        Returns:
            Dictionary mapping client names to connection status (True/False)
        """
        results = {}

        for client_name, client in self.clients.items():
            try:
                logger.info(f"Testing connection to {client_name}...")
                tools = await asyncio.wait_for(client.list_tools(), timeout=5.0)
                results[client_name] = True
                logger.info(f"{client_name}: OK ({len(tools)} tools)")
            except Exception as e:
                results[client_name] = False
                logger.error(f"{client_name}: FAILED - {e}")

        return results

    # ========================================================================
    # Configuration
    # ========================================================================

    def set_tool_timeout(self, tool_name: str, timeout: float) -> None:
        """
        Set a custom timeout for a specific tool.

        Args:
            tool_name: Name of the tool
            timeout: Timeout in seconds
        """
        self.tool_timeouts[tool_name] = timeout
        logger.debug(f"Set timeout for '{tool_name}' to {timeout}s")

    def get_tool_timeout(self, tool_name: str) -> float:
        """
        Get the configured timeout for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Timeout in seconds
        """
        return self.tool_timeouts.get(tool_name, self.default_timeout)
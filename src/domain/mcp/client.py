"""
MCP Client - Refactored wrapper for Model Context Protocol client.

This module provides a clean, type-safe wrapper around the MCP SDK,
maintaining compatibility with sampling callbacks while following
Clean Architecture principles.

REFACTORING FROM V1:
- V1: mcp_client.py with mixed concerns
- V2: Clean separation with proper error handling and logging
- Implements MCPClientProtocol for dependency inversion
"""

import sys
import asyncio
import json
import logging
from typing import Optional, Any, Dict, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.session import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    TextContent,
    Role,
)
from pydantic import AnyUrl

from src.infrastructure.llm.base import LLMProvider
from src.infrastructure.llm.message_converter import MessageConverter
from src.shared.exceptions import (
    MCPConnectionError,
    MCPServerError,
    MCPTimeoutError,
)

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP Client wrapper with clean interface.

    This client handles:
    - Connection management to MCP servers
    - Tool listing and execution
    - Resource access
    - Prompt management
    - Sampling callbacks (for server-initiated LLM calls)
    """

    def __init__(
            self,
            command: str,
            args: List[str],
            env: Optional[Dict[str, str]] = None,
            openrouter_client: Optional[LLMProvider] = None,
            name: str = "mcp_client",
    ):
        """
        Initialize MCP client.

        Args:
            command: Command to start MCP server (e.g., "uv", "python")
            args: Arguments for the command (e.g., ["run", "mcp_server.py"])
            env: Optional environment variables
            openrouter_client: LLM provider for sampling callbacks
            name: Client name for logging
        """
        self._command = command
        self._args = args
        self._env = env
        self._openrouter_client = openrouter_client
        self._name = name

        self._session: Optional[ClientSession] = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

        print(f"MCP Client '{name}' initialized (not connected yet)")
        logger.info(f"MCP Client '{name}' initialized (not connected yet)")

    # ========================================================================
    # Connection Management
    # ========================================================================

    """
    MCP Client - Connection snippet with timeout.
    
    Add this timeout logic to your src/domain/mcp/client.py
    """

    # In src/domain/mcp/client.py, modifica il metodo connect():

    async def connect(self) -> None:
        """
        Connect to the MCP server.

        Raises:
            MCPConnectionError: If connection fails
            MCPTimeoutError: If connection times out
        """
        try:
            logger.info(f"Connecting to MCP server '{self._name}': {self._command} {' '.join(self._args)}")

            # Setup server parameters
            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
            )

            # Connect via stdio with timeout
            stdio_transport = await asyncio.wait_for(
                self._exit_stack.enter_async_context(stdio_client(server_params)),
                timeout=10.0  # 10 seconds timeout
            )

            stdio_read, stdio_write = stdio_transport
            logger.info(f"Stdio transport established for '{self._name}'")

            # Create session with sampling callback
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(
                    stdio_read,
                    stdio_write,
                    sampling_callback=self._sampling_callback,
                )
            )

            logger.info(f"Initializing MCP client session '{self._name}'...")

            # Initialize session with timeout
            await asyncio.wait_for(
                self._session.initialize(),
                timeout=15.0  # 15 seconds timeout for initialization
            )

            logger.info(f"✓ MCP client '{self._name}' connected successfully")

        except asyncio.TimeoutError as e:
            error_msg = f"Timeout connecting to MCP server '{self._name}'"
            logger.error(error_msg)
            raise MCPTimeoutError(
                error_msg,
                details={"command": self._command, "args": self._args}
            ) from e
        except Exception as e:
            logger.error(f"Failed to connect MCP client '{self._name}': {e}")
            raise MCPConnectionError(
                f"Failed to connect to MCP server: {e}",
                details={"command": self._command, "args": self._args},
            ) from e

    async def cleanup(self) -> None:
        """
        Cleanup and close MCP connection.
        """
        logger.info(f"Cleaning up MCP client '{self._name}'")

        try:
            self._session = None

            # Close the exit stack that manages all context managers
            await self._exit_stack.aclose()

            # On Windows, wait for subprocesses to fully close
            if sys.platform == "win32":
                await asyncio.sleep(0.3)

            logger.info(f"MCP client '{self._name}' cleanup completed")

        except Exception as e:
            logger.warning(f"Error during cleanup of '{self._name}': {e}")

    # ========================================================================
    # Session Access
    # ========================================================================

    def _get_session(self) -> ClientSession:
        """
        Get active session.

        Returns:
            Active ClientSession

        Raises:
            ConnectionError: If session not initialized
        """
        if self._session is None:
            raise ConnectionError(
                f"MCP client '{self._name}' session not initialized. "
                "Call connect() first."
            )
        return self._session

    # ========================================================================
    # Tool Operations
    # ========================================================================

    async def list_tools(self) -> List[types.Tool]:
        """
        List available tools from MCP server.

        Returns:
            List of Tool objects

        Raises:
            MCPServerError: If listing fails
        """
        try:
            result = await self._get_session().list_tools()
            logger.debug(f"Listed {len(result.tools)} tools from '{self._name}'")
            return result.tools
        except Exception as e:
            logger.error(f"Failed to list tools from '{self._name}': {e}")
            raise MCPServerError(
                f"Failed to list tools: {e}",
                details={"client": self._name},
            ) from e

    async def call_tool(
            self, tool_name: str, tool_input: Dict[str, Any]
    ) -> types.CallToolResult:
        """
        Execute a tool on the MCP server.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result

        Raises:
            MCPServerError: If tool execution fails
            asyncio.CancelledError: If execution is cancelled
        """
        try:
            # Verify session is active
            session = self._get_session()

            logger.debug(f"Calling tool '{tool_name}' on '{self._name}'")

            result = await session.call_tool(tool_name, tool_input)

            logger.debug(f"Tool '{tool_name}' completed successfully")
            return result

        except asyncio.CancelledError:
            logger.warning(f"Tool call '{tool_name}' was cancelled")
            raise

        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}' on '{self._name}': {e}")
            raise MCPServerError(
                f"Tool execution failed: {e}",
                details={"tool_name": tool_name, "client": self._name},
            ) from e

    # ========================================================================
    # Prompt Operations
    # ========================================================================

    async def list_prompts(self) -> List[types.Prompt]:
        """
        List available prompts from MCP server.

        Returns:
            List of Prompt objects

        Raises:
            MCPServerError: If listing fails
        """
        try:
            result = await self._get_session().list_prompts()
            logger.debug(f"Listed {len(result.prompts)} prompts from '{self._name}'")
            return result.prompts
        except Exception as e:
            logger.error(f"Failed to list prompts from '{self._name}': {e}")
            raise MCPServerError(
                f"Failed to list prompts: {e}",
                details={"client": self._name},
            ) from e

    async def get_prompt(
            self, prompt_name: str, args: Dict[str, str]
    ) -> List[types.PromptMessage]:
        """
        Get a prompt with parameters.

        Args:
            prompt_name: Name of the prompt
            args: Arguments for the prompt

        Returns:
            List of prompt messages

        Raises:
            MCPServerError: If prompt retrieval fails
        """
        try:
            result = await self._get_session().get_prompt(prompt_name, args)
            logger.debug(f"Retrieved prompt '{prompt_name}' from '{self._name}'")
            return result.messages
        except Exception as e:
            logger.error(f"Failed to get prompt '{prompt_name}' from '{self._name}': {e}")
            raise MCPServerError(
                f"Failed to get prompt: {e}",
                details={"prompt_name": prompt_name, "client": self._name},
            ) from e

    # ========================================================================
    # Resource Operations
    # ========================================================================

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from MCP server.

        Returns:
            List of resource dictionaries

        Raises:
            MCPServerError: If listing fails
        """
        try:
            result = await self._get_session().list_resources()
            resources = [res.model_dump() for res in result.resources]
            logger.debug(f"Listed {len(resources)} resources from '{self._name}'")
            return resources
        except Exception as e:
            logger.error(f"Failed to list resources from '{self._name}': {e}")
            raise MCPServerError(
                f"Failed to list resources: {e}",
                details={"client": self._name},
            ) from e

    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource content (parsed JSON if applicable, otherwise text)

        Raises:
            MCPServerError: If reading fails
        """
        try:
            logger.debug(f"Reading resource '{uri}' from '{self._name}'")

            result = await self._get_session().read_resource(AnyUrl(uri))

            if not result.contents:
                return None

            resource = result.contents[0]

            # Handle different content types
            if isinstance(resource, types.TextResourceContents):
                # Try to parse as JSON first
                if resource.mimeType == "application/json":
                    try:
                        return json.loads(resource.text)
                    except json.JSONDecodeError:
                        return resource.text

                # Fallback to text
                return resource.text

            # For other types, return as-is
            return resource

        except Exception as e:
            logger.error(f"Failed to read resource '{uri}' from '{self._name}': {e}")
            raise MCPServerError(
                f"Failed to read resource: {e}",
                details={"uri": uri, "client": self._name},
            ) from e

    # ========================================================================
    # Sampling Callback (for server-initiated LLM calls)
    # ========================================================================

    async def _sampling_callback(
            self,
            context: RequestContext,
            params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        """
        Handle sampling requests from MCP server.

        This callback is invoked when the MCP server needs the LLM
        to generate a response (server-initiated sampling).

        Args:
            context: Request context
            params: Sampling parameters

        Returns:
            Generated message result
        """
        if not self._openrouter_client:
            logger.error("Sampling callback invoked but no LLM provider configured")
            return CreateMessageResult(
                role="assistant",
                model="unknown",
                content=TextContent(
                    type="text",
                    text="Error: No LLM provider configured for sampling",
                ),
            )

        try:
            logger.info(f"Sampling request received from MCP server '{self._name}'")

            # Convert MCP messages to LLM format
            messages = []
            for msg in params.messages:
                role = msg.role

                # Extract text content
                if hasattr(msg.content, "text"):
                    text = msg.content.text
                else:
                    text = str(msg.content)

                messages.append({"role": role, "content": text})

            logger.debug(f"Calling LLM for sampling with {len(messages)} message(s)")

            # Call LLM
            response = await self._openrouter_client.chat(
                messages=messages,
                temperature=getattr(params, "temperature", 0.7),
                max_tokens=getattr(params, "maxTokens", 1000),
            )

            # Extract text from response
            response_text = MessageConverter.extract_text_from_content(response.content)

            logger.info(f"Sampling completed successfully")

            # Return in MCP format
            return CreateMessageResult(
                role="assistant",
                model=self._openrouter_client.model,
                content=TextContent(type="text", text=response_text),
            )

        except Exception as e:
            logger.error(f"Error during sampling callback: {e}")
            return CreateMessageResult(
                role="assistant",
                model=self._openrouter_client.model if self._openrouter_client else "unknown",
                content=TextContent(
                    type="text",
                    text=f"Error during generation: {str(e)}",
                ),
            )

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def name(self) -> str:
        """Get client name."""
        return self._name

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._session is not None

"""
Protocols (interfaces) for MCP components.

These define the contracts that MCP-related components must implement,
enabling dependency inversion and easier testing.
"""

from typing import Protocol, List, Dict, Any, Optional
from abc import abstractmethod


# ============================================================================
# MCP Client Protocol
# ============================================================================


class MCPClientProtocol(Protocol):
    """
    Protocol defining the interface for MCP clients.

    This allows for different MCP client implementations while maintaining
    a consistent interface for the domain layer.
    """

    @abstractmethod
    async def list_tools(self) -> List[Any]:
        """
        List all available tools from the MCP server.

        Returns:
            List of tool objects
        """
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result
        """
        ...

    @abstractmethod
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources.

        Returns:
            List of resource dictionaries
        """
        ...

    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """
        Read the content of a resource.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        ...

    @abstractmethod
    async def list_prompts(self) -> List[Any]:
        """
        List all available prompts.

        Returns:
            List of prompt objects
        """
        ...

    @abstractmethod
    async def get_prompt(self, prompt_name: str, args: Dict[str, str]) -> List[Any]:
        """
        Get a prompt with parameters.

        Args:
            prompt_name: Name of the prompt
            args: Arguments for the prompt

        Returns:
            List of prompt messages
        """
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources and close connections."""
        ...


# ============================================================================
# Resource Manager Protocol
# ============================================================================


class ResourceManagerProtocol(Protocol):
    """
    Protocol for managing resources (documents, files, etc.).
    """

    @abstractmethod
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources.

        Returns:
            List of resource metadata
        """
        ...

    @abstractmethod
    async def get_resource(self, resource_id: str) -> Optional[str]:
        """
        Get the content of a resource by ID.

        Args:
            resource_id: Resource identifier

        Returns:
            Resource content or None if not found
        """
        ...

    @abstractmethod
    async def resource_exists(self, resource_id: str) -> bool:
        """
        Check if a resource exists.

        Args:
            resource_id: Resource identifier

        Returns:
            True if resource exists
        """
        ...


# ============================================================================
# Prompt Manager Protocol
# ============================================================================


class PromptManagerProtocol(Protocol):
    """
    Protocol for managing prompts.
    """

    @abstractmethod
    async def list_prompts(self) -> List[Any]:
        """
        List all available prompts.

        Returns:
            List of prompt objects
        """
        ...

    @abstractmethod
    async def get_prompt(self, prompt_name: str, params: Dict[str, str]) -> List[Any]:
        """
        Get a prompt with parameters.

        Args:
            prompt_name: Name of the prompt
            params: Parameters for the prompt

        Returns:
            List of prompt messages
        """
        ...

    @abstractmethod
    async def prompt_exists(self, prompt_name: str) -> bool:
        """
        Check if a prompt exists.

        Args:
            prompt_name: Prompt name

        Returns:
            True if prompt exists
        """
        ...


# ============================================================================
# Tool Executor Protocol
# ============================================================================


class ToolExecutorProtocol(Protocol):
    """
    Protocol for executing tools.
    """

    @abstractmethod
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get all available tools.

        Returns:
            List of tool schemas
        """
        ...

    @abstractmethod
    async def execute_tool(
            self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single tool.

        Args:
            tool_name: Tool name
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        ...

    @abstractmethod
    async def execute_tools(
            self, tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tools.

        Args:
            tool_calls: List of tool calls to execute

        Returns:
            List of tool execution results
        """
        ...
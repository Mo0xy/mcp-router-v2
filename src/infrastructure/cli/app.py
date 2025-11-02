"""
CLI Application - Command Line Interface for MCP Router.

Location: src/infrastructure/cli/app.py

This module provides an interactive CLI for chatting with the AI
through the MCP Router system.

REFACTORING FROM V1:
- V1: core/cli.py with mixed concerns
- V2: Clean CLI app with separation of concerns
"""

import asyncio
import sys
from typing import Optional, Union
from colorama import Fore, init as colorama_init
from src.infrastructure.cli.adapter import CliAdapter
from src.infrastructure.llm.models import LLMResponse

# Initialize colorama for cross-platform colored output
colorama_init(autoreset=True)


class CliApp:
    """
    Interactive CLI application for MCP Router.

    Features:
    - Interactive chat with AI
    - Command history
    - Resource mentions (@resource)
    - Prompt commands (/command)
    - Tool execution
    """

    def __init__(self, cli_adapter: CliAdapter):
        """
        Initialize CLI application.

        Args:
            cli_adapter: CliAdapter instance for chat processing
        """
        self.cli_adapter = cli_adapter
        self.running = False

    async def initialize(self) -> None:
        """Initialize the CLI application."""
        print(f"{Fore.LIGHTCYAN_EX}=" * 60)
        print(f"{Fore.LIGHTCYAN_EX}🤖 MCP Router V2 - Interactive CLI")
        print(f"{Fore.LIGHTCYAN_EX}=" * 60)
        print()
        await self._show_welcome_message()

    async def _show_welcome_message(self) -> None:
        """Display welcome message and available commands."""
        print(f"{Fore.LIGHTGREEN_EX}✓ System initialized successfully!")
        print()
        print(f"{Fore.YELLOW}Available features:")
        print(f"{Fore.YELLOW}  • Chat naturally with the AI")
        print(f"{Fore.YELLOW}  • Use @resource to reference documents/files")
        print(f"{Fore.YELLOW}  • Use /command for prompts (e.g., /summarize)")
        print(f"{Fore.YELLOW}  • Type 'help' for more commands")
        print(f"{Fore.YELLOW}  • Type 'exit' or Ctrl+C to quit")
        print()

        # Show available tools
        try:
            tools = await self.cli_adapter.list_available_tools()
            if tools:
                print(f"{Fore.CYAN}Available tools ({len(tools)}):")
                for tool in tools[:10]:  # Show first 10
                    print(f"{Fore.CYAN}  • {tool}")
                if len(tools) > 10:
                    print(f"{Fore.CYAN}  ... and {len(tools) - 10} more")
                print()
        except Exception as e:
            print(f"{Fore.RED}Warning: Could not list tools: {e}")
            print()

    async def run(self) -> None:
        """
        Main CLI loop.

        Continuously reads user input and processes messages.
        """
        self.running = True

        try:
            while self.running:
                # Read user input
                user_input = await self._get_user_input()

                if not user_input:
                    continue

                # Handle commands
                if await self._handle_command(user_input):
                    continue

                # Process chat message
                await self._process_message(user_input)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted by user")
        except Exception as e:
            print(f"{Fore.RED}Error in CLI loop: {e}")
        finally:
            await self.cleanup()

    async def _get_user_input(self) -> str:
        """
        Get input from user.

        Returns:
            User input string
        """
        try:
            # Use asyncio to run input in executor (non-blocking)
            loop = asyncio.get_event_loop()
            user_input = await loop.run_in_executor(
                None,
                lambda: input(f"{Fore.LIGHTBLUE_EX}You: ")
            )
            return user_input.strip()
        except EOFError:
            return "exit"

    async def _handle_command(self, user_input: str) -> bool:
        """
        Handle special commands.

        Args:
            user_input: User input string

        Returns:
            True if command was handled, False otherwise
        """
        command = user_input.lower()

        # Exit commands
        if command in ["exit", "quit", "bye"]:
            print(f"{Fore.YELLOW}Goodbye! 👋")
            self.running = False
            return True

        # Help command
        if command == "help":
            await self._show_help()
            return True

        # List tools
        if command == "tools":
            await self._list_tools()
            return True

        # List resources
        if command == "resources":
            await self._list_resources()
            return True

        # List prompts
        if command == "prompts":
            await self._list_prompts()
            return True

        # Show history
        if command == "history":
            await self._show_history()
            return True

        # Clear screen
        if command == "clear":
            self._clear_screen()
            return True

        return False

    async def _process_message(self, message: Union[str, LLMResponse]) -> None:
        """
        Process a user message.

        Args:
            user_input: User input string
        """
        print(f"{Fore.LIGHTMAGENTA_EX}AI: ", end="", flush=True)

        try:
            # Process message through adapter
            response = await self.cli_adapter.process_message(message)

            # Print response
            print(f"{Fore.LIGHTMAGENTA_EX}{response.response}")


        except Exception as e:
            print(f"{Fore.RED}Error: {e}")
            print()

    # ========================================================================
    # Command Handlers
    # ========================================================================

    async def _show_help(self) -> None:
        """Show help message."""
        print(f"\n{Fore.LIGHTCYAN_EX}=== MCP Router V2 Help ===")
        print(f"\n{Fore.YELLOW}Commands:")
        print(f"{Fore.YELLOW}  help       - Show this help message")
        print(f"{Fore.YELLOW}  tools      - List available tools")
        print(f"{Fore.YELLOW}  resources  - List available resources")
        print(f"{Fore.YELLOW}  prompts    - List available prompts")
        print(f"{Fore.YELLOW}  history    - Show conversation history")
        print(f"{Fore.YELLOW}  clear      - Clear screen")
        print(f"{Fore.YELLOW}  exit       - Exit the application")
        print(f"\n{Fore.CYAN}Features:")
        print(f"{Fore.CYAN}  @resource  - Reference a document (e.g., @report.pdf)")
        print(f"{Fore.CYAN}  /command   - Execute a prompt (e.g., /summarize doc_123)")
        print()

    async def _list_tools(self) -> None:
        """List all available tools."""
        try:
            tools = await self.cli_adapter.list_available_tools()

            if not tools:
                print(f"{Fore.YELLOW}No tools available")
                return

            print(f"\n{Fore.LIGHTCYAN_EX}=== Available Tools ({len(tools)}) ===")
            for i, tool in enumerate(tools, 1):
                print(f"{Fore.CYAN}{i}. {tool}")
            print()

        except Exception as e:
            print(f"{Fore.RED}Error listing tools: {e}")
            print()

    async def _list_resources(self) -> None:
        """List all available resources."""
        try:
            resources = await self.cli_adapter.list_available_resources()

            if not resources:
                print(f"{Fore.YELLOW}No resources available")
                return

            print(f"\n{Fore.LIGHTCYAN_EX}=== Available Resources ({len(resources)}) ===")
            for i, resource in enumerate(resources, 1):
                name = resource.get("name", "Unknown")
                uri = resource.get("uri", "")
                print(f"{Fore.CYAN}{i}. {name} ({uri})")
            print()

        except Exception as e:
            print(f"{Fore.RED}Error listing resources: {e}")
            print()

    async def _list_prompts(self) -> None:
        """List all available prompts."""
        try:
            prompts = await self.cli_adapter.list_available_prompts()

            if not prompts:
                print(f"{Fore.YELLOW}No prompts available")
                return

            print(f"\n{Fore.LIGHTCYAN_EX}=== Available Prompts ({len(prompts)}) ===")
            for i, prompt in enumerate(prompts, 1):
                name = prompt.name if hasattr(prompt, 'name') else str(prompt)
                desc = prompt.description if hasattr(prompt, 'description') else ""
                print(f"{Fore.CYAN}{i}. /{name} - {desc}")
            print()

        except Exception as e:
            print(f"{Fore.RED}Error listing prompts: {e}")
            print()

    async def _show_history(self) -> None:
        """Show conversation history."""
        try:
            history = self.cli_adapter.get_conversation_history()

            if not history:
                print(f"{Fore.YELLOW}No conversation history yet")
                return

            print(f"\n{Fore.LIGHTCYAN_EX}=== Conversation History ===")
            for i, message in enumerate(history, 1):
                role = message.get("role", "unknown")
                content = message.get("content", "")

                # Truncate long messages
                if len(content) > 100:
                    content = content[:97] + "..."

                color = Fore.LIGHTBLUE_EX if role == "user" else Fore.LIGHTMAGENTA_EX
                print(f"{color}{i}. {role.upper()}: {content}")
            print()

        except Exception as e:
            print(f"{Fore.RED}Error showing history: {e}")
            print()

    def _clear_screen(self) -> None:
        """Clear the terminal screen."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Fore.LIGHTCYAN_EX}🤖 MCP Router V2 - Interactive CLI")
        print()

    # ========================================================================
    # Cleanup
    # ========================================================================

    async def cleanup(self) -> None:
        """Cleanup resources."""
        print(f"{Fore.CYAN}Cleaning up...")
        # Add any cleanup logic here
        print(f"{Fore.GREEN}✓ Cleanup completed")
"""
Main Entry Point - CLI Mode for MCP Router V2.

Location: main.py (project root)

This is the entry point for running MCP Router in CLI (Command Line Interface) mode.

Usage:
    python main.py
    or
    uv run main.py

REFACTORING FROM V1:
- V1: Mixed initialization and execution logic
- V2: Clean separation with dependency injection
- Uses v2 architecture (services, adapters, etc.)
"""

import asyncio
import sys

from src.domain.conversation.manager import ConversationManager
from src.domain.conversation.storage.memory import InMemoryConversationStorage
from typing import Dict
from dotenv import load_dotenv
from colorama import Fore, init as colorama_init

# V2 imports - Clean Architecture layers
from src.config.settings import get_settings
from src.infrastructure.llm.openrouter import OpenRouterClient
from src.infrastructure.database.connection import get_db_manager, close_db_manager
from src.infrastructure.database.repository import DatabaseRepository
from src.domain.mcp.client import MCPClient
from src.domain.tools.manager import ToolManager
from src.domain.chat.service import ChatService
from src.infrastructure.cli.adapter import CliAdapter
from src.infrastructure.cli.app import CliApp

# Initialize colorama
colorama_init(autoreset=True)

# Load environment variables
load_dotenv()


async def test_system_health(
        clients: Dict[str, MCPClient],
        openrouter_client: OpenRouterClient,
        db_repo: DatabaseRepository
) -> bool:
    """
    Test the health of all system components.
    
    Args:
        clients: Dictionary of MCP clients
        openrouter_client: OpenRouter LLM client
        db_repo: Database repository
        
    Returns:
        True if all systems healthy, False otherwise
    """
    print(f"{Fore.CYAN}=== System Health Check ===")

    all_healthy = True

    # Test OpenRouter connection
    try:
        test_messages = [{"role": "user", "content": "Hello"}]
        response = await openrouter_client.chat(test_messages, max_tokens=10)
        print(f"{Fore.GREEN}✓ OpenRouter: Connected")
    except Exception as e:
        print(f"{Fore.RED}✗ OpenRouter: Failed - {e}")
        all_healthy = False

    # Test Database connection
    try:
        if db_repo.health_check():
            print(f"{Fore.GREEN}✓ Database: Connected")
        else:
            print(f"{Fore.RED}✗ Database: Health check failed")
            all_healthy = False
    except Exception as e:
        print(f"{Fore.RED}✗ Database: Failed - {e}")
        all_healthy = False

    # Test MCP clients
    tool_manager = ToolManager(clients)
    health_results = await tool_manager.test_connections()
    for client_name, is_healthy in health_results.items():
        if is_healthy:
            print(f"{Fore.GREEN}✓ MCP Client '{client_name}': Connected")
        else:
            print(f"{Fore.RED}✗ MCP Client '{client_name}': Failed")
            all_healthy = False

    if all_healthy:
        print(f"{Fore.GREEN}✓ All systems healthy")
    else:
        print(f"{Fore.YELLOW}⚠ Some systems have issues")

    print()
    return all_healthy


async def main():
    """Main entry point for CLI mode."""

    print(f"{Fore.LIGHTCYAN_EX}")
    print("=" * 70)
    print("🚀 MCP Router V2 - Starting in CLI Mode")
    print("=" * 70)
    print()

    # ========================================================================
    # Step 1: Load Configuration
    # ========================================================================

    print(f"{Fore.CYAN}📋 Loading configuration...")
    settings = get_settings()

    # Validate critical settings
    if not settings.openrouter_api_key:
        print(f"{Fore.RED}ERROR: OPENROUTER_API_KEY not set in environment")
        sys.exit(1)

    print(f"{Fore.GREEN}✓ Configuration loaded")
    print(f"{Fore.CYAN}  Model: {settings.model}")
    print(f"{Fore.CYAN}  API Key: {settings.openrouter_api_key[:20]}...")
    print()

    # ========================================================================
    # Step 2: Initialize Database
    # ========================================================================

    print(f"{Fore.CYAN}🗄️ Initializing database...")

    try:
        db_manager = get_db_manager()
        db_repo = DatabaseRepository(db_manager)
        print(f"{Fore.GREEN}✓ Database initialized")
    except Exception as e:
        print(f"{Fore.RED}✗ Database initialization failed: {e}")
        print(f"{Fore.YELLOW}⚠ Continuing without database (some features may not work)")
        db_repo = None

    print()

    # ========================================================================
    # Step 3: Initialize OpenRouter LLM Client
    # ========================================================================

    print(f"{Fore.CYAN}🤖 Initializing OpenRouter client...")

    openrouter_client = OpenRouterClient(
        model=settings.model,
        api_key=settings.openrouter_api_key,
        default_timeout=settings.default_timeout,
    )

    print(f"{Fore.GREEN}✓ OpenRouter client initialized")
    print()

    # ========================================================================
    # Step 4: Initialize MCP Clients
    # ========================================================================

    print(f"{Fore.CYAN}🔌 Initializing MCP clients...")

    clients = {}

    try:
        # Initialize HR/Interview MCP client
        hr_client = MCPClient(
            command=settings.mcp_server_command,
            args=settings.mcp_server_args,
            env=None,
            openrouter_client=openrouter_client,
            name="interview_bot"
        )
        await hr_client.connect()
        clients["interview_bot"] = hr_client

        print(f"{Fore.GREEN}✓ MCP client 'interview_bot' connected")

    except Exception as e:
        print(f"{Fore.RED}✗ MCP client initialization failed: {e}")
        print(f"{Fore.YELLOW}⚠ Continuing without MCP clients")

    print()

    # ========================================================================
    # Step 5: System Health Check
    # ========================================================================

    if clients:
        await test_system_health(clients, openrouter_client, db_repo)

    # ========================================================================
    # Step 6: Initialize Domain Services
    # ========================================================================

    print(f"{Fore.CYAN}⚙️ Initializing services...")

    # Create ToolManager
    tool_manager = ToolManager(clients)
    conv_stor = InMemoryConversationStorage()
    conv_man = ConversationManager(conv_stor)

    # Create ChatService
    chat_service = ChatService(
        llm_provider=openrouter_client,
        conversation_manager=conv_man,
        tool_manager=tool_manager,
        mcp_clients=clients,
    )

    print(f"{Fore.GREEN}✓ Chat service initialized")
    print()

    # ========================================================================
    # Step 7: Initialize CLI Infrastructure
    # ========================================================================

    print(f"{Fore.CYAN}💻 Initializing CLI interface...")

    # Create CLI Adapter
    cli_adapter = CliAdapter(
        chat_service=chat_service,
        mcp_clients=clients,
        conversation_manager=conv_man
    )

    await cli_adapter.initialize()

    # Create CLI App
    cli_app = CliApp(cli_adapter)

    await cli_app.initialize()

    # ========================================================================
    # Step 8: Run CLI Application
    # ========================================================================

    try:
        await cli_app.run()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # ====================================================================
        # Cleanup
        # ====================================================================
        print(f"\n{Fore.CYAN}🧹 Cleaning up...")

        # Close MCP clients
        for client_name, client in clients.items():
            try:
                await client.cleanup()
                print(f"{Fore.GREEN}✓ Closed MCP client '{client_name}'")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ Warning during {client_name} cleanup: {e}")

        # Close database connection
        if db_repo:
            try:
                close_db_manager()
                print(f"{Fore.GREEN}✓ Closed database connection")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ Warning during database cleanup: {e}")

        print(f"{Fore.GREEN}✓ Cleanup completed")
        print(f"{Fore.LIGHTGREEN_EX}Goodbye! 👋")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Set Windows event loop policy if needed
    if sys.platform == "win32":
        # asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

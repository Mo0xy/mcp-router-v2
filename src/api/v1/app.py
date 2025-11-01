"""
FastAPI application factory.

This module creates and configures the FastAPI application using
the factory pattern for better testability and flexibility.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time

from src.api.v1.routes import router as api_router
from src.api.v1.dependencies import lifespan_manager
from src.config.settings import Settings, get_settings
from src.config.logging_config import setup_logging
from src.shared.exceptions import MCPRouterException

logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Handler
# ============================================================================


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Manages startup and shutdown events.
    """
    settings = get_settings()

    # Setup logging
    setup_logging(settings)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize resources via lifespan manager
    async with lifespan_manager(settings):
        logger.info("Application ready to accept requests")
        yield

    logger.info("Application shutdown complete")


# ============================================================================
# Application Factory
# ============================================================================


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        settings: Optional settings instance (uses default if not provided)

    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        MCP Router API - Model Context Protocol integration with OpenRouter
        
        ## Features
        * 🤖 Chat with AI models via OpenRouter
        * 🛠️ Dynamic tool execution via MCP
        * 📚 Resource access (documents, files, etc.)
        * 🔄 Multi-iteration conversations with tool use
        
        ## Architecture
        Built with Clean Architecture principles:
        - **Domain Layer**: Business logic (chat, tools, MCP)
        - **Infrastructure Layer**: External services (LLM, MCP servers)
        - **API Layer**: FastAPI endpoints with dependency injection
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=app_lifespan,
        debug=settings.debug,
    )

    # Configure CORS
    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info(f"CORS enabled for origins: {settings.cors_origins_list}")

    # Add custom middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add processing time header to responses."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Exception handlers
    @app.exception_handler(MCPRouterException)
    async def mcp_router_exception_handler(request: Request, exc: MCPRouterException):
        """Handle custom MCP Router exceptions."""
        logger.error(f"MCPRouterException: {exc.message}", extra={"details": exc.details})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )

    # Root endpoint - redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect to API documentation."""
        return RedirectResponse(url="/docs")

    # Include API routes
    app.include_router(api_router, prefix="/v1", tags=["v1"])

    logger.info("FastAPI application configured successfully")

    return app


# ============================================================================
# Application Instance (for uvicorn)
# ============================================================================


# Create default app instance
app = create_app()


# ============================================================================
# For development/testing
# ============================================================================


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.api.v1.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
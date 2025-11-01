"""
Application settings using Pydantic Settings.

This module provides type-safe configuration management using
environment variables and .env files.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # ========================================================================
    # LLM Configuration
    # ========================================================================

    model: str = "deepseek/deepseek-chat-v3.1:free"
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ========================================================================
    # Application Configuration
    # ========================================================================

    app_name: str = "MCP Router API"
    app_version: str = "2.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ========================================================================
    # API Server Configuration
    # ========================================================================

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # ========================================================================
    # Request Configuration
    # ========================================================================

    default_timeout: float = 120.0
    max_retries: int = 3
    max_iterations: int = 5
    default_temperature: float = 0.4
    default_max_tokens: int = 10000

    # ========================================================================
    # MCP Server Configuration
    # ========================================================================

    mcp_server_command: str = "uv"
    mcp_server_args: list[str] = ["run", "mcp_server.py"]   # Comma-separated

    # ========================================================================
    # Rate Limiting (future)
    # ========================================================================

    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 60

    # ========================================================================
    # CORS Configuration
    # ========================================================================

    cors_enabled: bool = True
    cors_origins: str = "*"  # Comma-separated origins

    # ========================================================================
    # Pydantic Settings Configuration
    # ========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # Computed Properties
    # ========================================================================

    @property
    def mcp_server_args_list(self) -> list[str]:
        """Convert comma-separated args to list."""
        return [arg.strip() for arg in self.mcp_server_args.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        """Convert comma-separated origins to list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # ========================================================================
    # Validation
    # ========================================================================

    def validate_settings(self) -> None:
        """
        Validate settings at startup.

        Raises:
            ValueError: If critical settings are invalid
        """
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        if self.default_timeout <= 0:
            raise ValueError("default_timeout must be > 0")

        if not (0.0 <= self.default_temperature <= 2.0):
            raise ValueError("default_temperature must be between 0.0 and 2.0")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function is cached to ensure we only load settings once.
    Use this in FastAPI dependencies.

    Returns:
        Settings instance
    """
    settings = Settings()
    settings.validate_settings()
    return settings


# For backwards compatibility / direct access
settings = get_settings()
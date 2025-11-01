"""
OpenRouter LLM Provider - Refactored Implementation.

This module provides a clean, refactored OpenRouter client that:
- Uses MessageConverter to eliminate code duplication
- Implements the LLMProvider interface
- Has proper error handling and retry logic
- Is fully type-hinted and testable

IMPROVEMENTS OVER ORIGINAL:
- Removed duplicated message conversion logic (now in MessageConverter)
- Separated retry logic into dedicated method
- Better error handling with custom exceptions
- Cleaner code structure following SRP
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from src.infrastructure.llm.base import LLMProvider
from src.infrastructure.llm.models import LLMResponse, ToolSchema
from src.infrastructure.llm.message_converter import MessageConverter
from src.shared.exceptions import (
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthenticationError,
)
from src.shared.constants import (
    OPENROUTER_BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
)


class OpenRouterClient(LLMProvider):
    """
    OpenRouter API client implementation.

    This client handles communication with OpenRouter's API, providing
    a clean interface for chat completions with tool support.
    """

    def __init__(
            self,
            model: str,
            api_key: str,
            base_url: str = OPENROUTER_BASE_URL,
            default_timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize OpenRouter client.

        Args:
            model: Model identifier (e.g., "anthropic/claude-3-sonnet")
            api_key: OpenRouter API key
            base_url: OpenRouter API base URL
            default_timeout: Default request timeout in seconds

        Raises:
            ValueError: If api_key is missing
        """
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._default_timeout = default_timeout

        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ========================================================================
    # LLMProvider Interface Implementation
    # ========================================================================

    @property
    def model(self) -> str:
        """Get the model identifier."""
        return self._model

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "OpenRouter"

    async def chat(
            self,
            messages: List[Dict[str, Any]],
            tools: Optional[List[ToolSchema]] = None,
            max_tokens: int = 10000,
            temperature: float = 0.4,
            **kwargs,
    ) -> LLMResponse:
        """
        Send a chat completion request to OpenRouter.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional OpenRouter parameters

        Returns:
            LLMResponse with model's response

        Raises:
            LLMProviderError: If the request fails
            LLMTimeoutError: If the request times out
            LLMAuthenticationError: If authentication fails
            LLMRateLimitError: If rate limit is exceeded
        """
        # Convert messages to OpenRouter format using MessageConverter
        openrouter_messages = MessageConverter.to_openrouter_messages(messages)

        # Build request payload
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": openrouter_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = [self._tool_to_openrouter_format(tool) for tool in tools]

        # Add any additional kwargs
        payload.update(kwargs)

        # Make the request
        try:
            async with httpx.AsyncClient(timeout=self._default_timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )

                # Handle HTTP errors
                if response.status_code == 401:
                    raise LLMAuthenticationError("Invalid API key")
                elif response.status_code == 429:
                    raise LLMRateLimitError("Rate limit exceeded")
                elif response.status_code >= 400:
                    error_detail = response.json().get("error", {}).get("message", "Unknown error")
                    raise LLMProviderError(
                        f"OpenRouter API error: {error_detail}",
                        details={"status_code": response.status_code},
                    )

                response.raise_for_status()

                # Parse response using MessageConverter
                response_data = response.json()
                return MessageConverter.from_openrouter_response(response_data)

        except httpx.TimeoutException as e:
            raise LLMTimeoutError("Request to OpenRouter timed out") from e
        except (LLMAuthenticationError, LLMRateLimitError, LLMProviderError):
            raise
        except Exception as e:
            raise LLMProviderError(f"Unexpected error: {str(e)}") from e

    async def chat_with_retry(
            self,
            messages: List[Dict[str, Any]],
            tools: Optional[List[ToolSchema]] = None,
            max_tokens: int = 10000,
            temperature: float = 0.4,
            max_retries: int = DEFAULT_MAX_RETRIES,
            **kwargs,
    ) -> LLMResponse:
        """
        Send a chat request with exponential backoff retry logic.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_retries: Maximum number of retry attempts
            **kwargs: Additional parameters

        Returns:
            LLMResponse with model's response

        Raises:
            LLMProviderError: If all retries fail
        """
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                return await self.chat(
                    messages=messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

            except LLMRateLimitError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = RETRY_BACKOFF_FACTOR ** attempt
                    await asyncio.sleep(delay)
                    continue
                raise

            except LLMTimeoutError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = RETRY_BACKOFF_FACTOR ** attempt
                    await asyncio.sleep(delay)
                    continue
                raise

            except LLMAuthenticationError:
                # Don't retry authentication errors
                raise

            except LLMProviderError as e:
                last_exception = e
                # Only retry on specific status codes
                if (
                        attempt < max_retries - 1
                        and e.details.get("status_code") in RETRY_STATUS_CODES
                ):
                    delay = RETRY_BACKOFF_FACTOR ** attempt
                    await asyncio.sleep(delay)
                    continue
                raise

        # If we get here, all retries failed
        raise LLMProviderError(
            f"All {max_retries} retries failed", details={"last_error": str(last_exception)}
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _tool_to_openrouter_format(self, tool: ToolSchema) -> Dict[str, Any]:
        """
        Convert ToolSchema to OpenRouter tool format.

        Args:
            tool: Tool schema in internal format

        Returns:
            Tool in OpenRouter format
        """
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }


# ============================================================================
# Convenience Functions (for backwards compatibility if needed)
# ============================================================================


async def warmup_model(client: OpenRouterClient) -> None:
    """
    Warm up the model with a simple request.

    This can help reduce latency on the first real request.

    Args:
        client: OpenRouter client instance
    """
    try:
        test_messages = [{"role": "user", "content": "Hello"}]
        await client.chat(messages=test_messages, max_tokens=10)
    except Exception:
        # Ignore warmup errors
        pass
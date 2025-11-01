"""
Abstract base class for LLM providers.

This module defines the contract that all LLM providers must implement,
enabling easy swapping of providers (e.g., OpenRouter, OpenAI, Anthropic).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.infrastructure.llm.models import LLMResponse, ToolSchema


class LLMProvider(ABC):
    """
    Abstract base class for Language Model providers.

    This interface defines the contract for interacting with any LLM provider,
    enabling the system to work with different providers without code changes.
    """

    @abstractmethod
    async def chat(
            self,
            messages: List[Dict[str, Any]],
            tools: Optional[List[ToolSchema]] = None,
            max_tokens: int = 10000,
            temperature: float = 0.4,
            **kwargs,
    ) -> LLMResponse:
        """
        Send a chat request to the LLM provider.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with model's response

        Raises:
            LLMProviderError: If the provider returns an error
            LLMTimeoutError: If the request times out
            LLMAuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def chat_with_retry(
            self,
            messages: List[Dict[str, Any]],
            tools: Optional[List[ToolSchema]] = None,
            max_tokens: int = 10000,
            temperature: float = 0.4,
            max_retries: int = 3,
            **kwargs,
    ) -> LLMResponse:
        """
        Send a chat request with automatic retry logic.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools available to the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            max_retries: Maximum number of retry attempts
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with model's response

        Raises:
            LLMProviderError: If all retries fail
            LLMTimeoutError: If the request times out
        """
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """
        Get the model identifier.

        Returns:
            Model identifier string
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get the provider name.

        Returns:
            Provider name (e.g., "OpenRouter", "OpenAI")
        """
        pass
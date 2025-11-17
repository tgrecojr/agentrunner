"""
Base LLM Provider Interface

Defines the abstract interface that all LLM providers must implement.
Supports pluggable architecture for Bedrock, OpenAI, Anthropic, and Ollama.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""

    provider: str  # bedrock, openai, anthropic, ollama
    model_id: str  # Specific model identifier
    temperature: float = 0.7
    max_tokens: int = 4096
    credentials: Dict[str, Any] = field(default_factory=dict)
    additional_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str  # Generated text content
    model: str  # Model that generated the response
    input_tokens: int  # Number of input tokens
    output_tokens: int  # Number of output tokens
    finish_reason: str  # stop, length, error, etc.
    cost_usd: float  # Estimated cost in USD
    metadata: Dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    All providers must implement:
    - complete(): Synchronous text completion
    - stream(): Asynchronous streaming completion
    - count_tokens(): Token counting
    - get_cost(): Cost calculation
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize the provider with configuration.

        Args:
            config: LLMConfig object with provider settings
        """
        self.config = config
        self.model_id = config.model_id
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion for the given prompt.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt/instruction
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            LLMProviderError: On provider-specific errors
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens as they're generated.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt/instruction
            **kwargs: Provider-specific parameters

        Yields:
            Chunks of generated text

        Raises:
            LLMProviderError: On provider-specific errors
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass

    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate the cost in USD for the given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pass

    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name (bedrock, openai, anthropic, ollama)
        """
        return self.config.provider

"""
Anthropic LLM Provider

Implements LLM provider for direct Anthropic API access with support for:
- Claude 3 models (Opus, Sonnet, Haiku)
- Claude 2 models

Uses anthropic SDK with native token counting support.
"""

from typing import AsyncIterator, Optional

from anthropic import Anthropic, AnthropicError, RateLimitError

from .base import LLMConfig, LLMProvider, LLMResponse
from .exceptions import (
    LLMAuthenticationError,
    LLMContextLengthExceededError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


class AnthropicProvider(LLMProvider):
    """
    Anthropic LLM provider implementation.

    Uses official Anthropic SDK with support for system prompts and tool use.
    """

    # Pricing per 1K tokens (as of 2024 - update as needed)
    PRICING = {
        # Claude 3 models
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        # Claude 2 models
        "claude-2.1": {"input": 0.008, "output": 0.024},
        "claude-2.0": {"input": 0.008, "output": 0.024},
        "claude-instant-1.2": {"input": 0.0008, "output": 0.0024},
    }

    def __init__(self, config: LLMConfig):
        """
        Initialize Anthropic provider.

        Args:
            config: LLMConfig with Anthropic credentials
        """
        super().__init__(config)

        # Initialize Anthropic client
        api_key = config.credentials.get("anthropic_api_key")

        self.client = Anthropic(
            api_key=api_key,
            timeout=config.additional_params.get("timeout", 60.0)
        )

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using Anthropic.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Anthropic parameters (tools, etc.)

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: On Anthropic API errors
        """
        try:
            # Build request parameters
            params = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # Add system prompt if provided
            if system_prompt:
                params["system"] = system_prompt

            # Add any additional parameters (tools, etc.)
            params.update(kwargs)

            # Call Anthropic API
            response = self.client.messages.create(**params)

            # Extract response data
            content = response.content[0].text if response.content else ""
            finish_reason = response.stop_reason

            # Get token counts
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Calculate cost
            cost = self.get_cost(input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                cost_usd=cost,
                metadata={
                    "provider": "anthropic",
                    "stop_reason": response.stop_reason,
                    "stop_sequence": response.stop_sequence
                }
            )

        except RateLimitError as e:
            raise LLMRateLimitError(
                str(e),
                provider="anthropic",
                original_error=e
            )

        except AnthropicError as e:
            self._handle_anthropic_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Anthropic completion: {str(e)}",
                provider="anthropic",
                original_error=e
            )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from Anthropic.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Anthropic parameters

        Yields:
            Chunks of generated text

        Raises:
            LLMProviderError: On Anthropic API errors
        """
        try:
            # Build request parameters
            params = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # Add system prompt if provided
            if system_prompt:
                params["system"] = system_prompt

            # Add any additional parameters
            params.update(kwargs)

            # Call Anthropic streaming API
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text

        except RateLimitError as e:
            raise LLMRateLimitError(
                str(e),
                provider="anthropic",
                original_error=e
            )

        except AnthropicError as e:
            self._handle_anthropic_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Anthropic streaming: {str(e)}",
                provider="anthropic",
                original_error=e
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Anthropic's count_tokens API.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count
        """
        try:
            # Use Anthropic's token counting API
            result = self.client.count_tokens(text)
            return result
        except Exception:
            # Fall back to character-based estimation
            # Anthropic models use ~3.5 characters per token on average
            return len(text) // 4

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for Anthropic model usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Find matching pricing entry
        pricing = None
        for key, value in self.PRICING.items():
            if key in self.model_id:
                pricing = value
                break

        if not pricing:
            # Default pricing if model not found
            pricing = {"input": 0.003, "output": 0.015}

        # Calculate cost per 1K tokens
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def _handle_anthropic_error(self, error: AnthropicError) -> None:
        """
        Map Anthropic errors to custom exception hierarchy.

        Args:
            error: Anthropic error

        Raises:
            Appropriate LLMProviderError subclass
        """
        error_message = str(error)

        # Check error type and message
        if "authentication" in error_message.lower() or "api key" in error_message.lower():
            raise LLMAuthenticationError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        elif "not found" in error_message.lower() or "does not exist" in error_message.lower():
            raise LLMModelNotFoundError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        elif "context" in error_message.lower() or "too long" in error_message.lower():
            raise LLMContextLengthExceededError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        elif "timeout" in error_message.lower():
            raise LLMTimeoutError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        elif "unavailable" in error_message.lower() or "503" in error_message or "500" in error_message:
            raise LLMServiceUnavailableError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        elif "invalid" in error_message.lower() or "bad request" in error_message.lower() or "400" in error_message:
            raise LLMInvalidRequestError(
                error_message,
                provider="anthropic",
                original_error=error
            )

        else:
            raise LLMProviderError(
                f"Anthropic API error: {error_message}",
                provider="anthropic",
                original_error=error
            )

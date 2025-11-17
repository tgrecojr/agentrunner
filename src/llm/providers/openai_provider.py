"""
OpenAI LLM Provider

Implements LLM provider for OpenAI with support for:
- GPT-4 models (GPT-4, GPT-4-Turbo)
- GPT-3.5 models (GPT-3.5-Turbo)

Uses openai SDK and tiktoken for accurate token counting.
"""

import asyncio
from typing import AsyncIterator, Optional

import tiktoken
from openai import OpenAI, OpenAIError, RateLimitError

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


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider implementation.

    Uses official OpenAI SDK with accurate token counting via tiktoken.
    """

    # Pricing per 1K tokens (as of 2024 - update as needed)
    PRICING = {
        # GPT-4 models
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-32k": {"input": 0.06, "output": 0.12},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        # GPT-3.5 models
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    }

    def __init__(self, config: LLMConfig):
        """
        Initialize OpenAI provider.

        Args:
            config: LLMConfig with OpenAI credentials
        """
        super().__init__(config)

        # Initialize OpenAI client
        api_key = config.credentials.get("openai_api_key")
        organization = config.credentials.get("openai_org_id")

        self.client = OpenAI(
            api_key=api_key,
            organization=organization,
            timeout=config.additional_params.get("timeout", 60.0)
        )

        # Initialize tokenizer for token counting
        try:
            self.encoder = tiktoken.encoding_for_model(self.model_id)
        except KeyError:
            # Fall back to cl100k_base for unknown models
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using OpenAI.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: On OpenAI API errors
        """
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call OpenAI API with retry logic
            max_retries = kwargs.pop("max_retries", 3)
            retry_count = 0

            while retry_count < max_retries:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model_id,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        **kwargs
                    )
                    break
                except RateLimitError as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** (retry_count - 1)
                    asyncio.sleep(wait_time)

            # Extract response data
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            # Get token counts
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

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
                    "provider": "openai",
                    "system_fingerprint": response.system_fingerprint
                }
            )

        except RateLimitError as e:
            raise LLMRateLimitError(
                str(e),
                provider="openai",
                original_error=e
            )

        except OpenAIError as e:
            self._handle_openai_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during OpenAI completion: {str(e)}",
                provider="openai",
                original_error=e
            )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from OpenAI.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters

        Yields:
            Chunks of generated text

        Raises:
            LLMProviderError: On OpenAI API errors
        """
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call OpenAI streaming API
            stream = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                **kwargs
            )

            # Stream chunks
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError as e:
            raise LLMRateLimitError(
                str(e),
                provider="openai",
                original_error=e
            )

        except OpenAIError as e:
            self._handle_openai_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during OpenAI streaming: {str(e)}",
                provider="openai",
                original_error=e
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count
        """
        return len(self.encoder.encode(text))

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for OpenAI model usage.

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
            pricing = {"input": 0.001, "output": 0.002}

        # Calculate cost per 1K tokens
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def _handle_openai_error(self, error: OpenAIError) -> None:
        """
        Map OpenAI errors to custom exception hierarchy.

        Args:
            error: OpenAI error

        Raises:
            Appropriate LLMProviderError subclass
        """
        error_message = str(error)

        # Check error type and message
        if "authentication" in error_message.lower() or "api key" in error_message.lower():
            raise LLMAuthenticationError(
                error_message,
                provider="openai",
                original_error=error
            )

        elif "not found" in error_message.lower() or "does not exist" in error_message.lower():
            raise LLMModelNotFoundError(
                error_message,
                provider="openai",
                original_error=error
            )

        elif "context length" in error_message.lower() or "maximum context" in error_message.lower():
            raise LLMContextLengthExceededError(
                error_message,
                provider="openai",
                original_error=error
            )

        elif "timeout" in error_message.lower():
            raise LLMTimeoutError(
                error_message,
                provider="openai",
                original_error=error
            )

        elif "service unavailable" in error_message.lower() or "500" in error_message:
            raise LLMServiceUnavailableError(
                error_message,
                provider="openai",
                original_error=error
            )

        elif "invalid" in error_message.lower() or "bad request" in error_message.lower():
            raise LLMInvalidRequestError(
                error_message,
                provider="openai",
                original_error=error
            )

        else:
            raise LLMProviderError(
                f"OpenAI API error: {error_message}",
                provider="openai",
                original_error=error
            )

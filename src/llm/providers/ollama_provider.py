"""
Ollama LLM Provider

Implements LLM provider for local Ollama models with support for:
- Llama 2/3 models
- Mistral models
- Any other Ollama-compatible models

Uses HTTP API for communication with local Ollama service.
"""

import json
from typing import AsyncIterator, Dict, Optional

import httpx

from .base import LLMConfig, LLMProvider, LLMResponse
from .exceptions import (
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider implementation.

    Connects to local Ollama service via HTTP API.
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Ollama provider.

        Args:
            config: LLMConfig with Ollama settings
        """
        super().__init__(config)

        # Get Ollama host from config
        self.host = config.credentials.get("ollama_host", "http://localhost:11434")
        self.timeout = config.additional_params.get("timeout", 120.0)

        # Initialize HTTP client
        self.client = httpx.Client(
            base_url=self.host,
            timeout=self.timeout
        )

        # Verify Ollama is accessible
        self._check_health()

    def _check_health(self) -> None:
        """
        Check if Ollama service is accessible.

        Raises:
            LLMServiceUnavailableError: If Ollama is not accessible
        """
        try:
            response = self.client.get("/api/tags")
            if response.status_code != 200:
                raise LLMServiceUnavailableError(
                    f"Ollama service returned status {response.status_code}",
                    provider="ollama"
                )
        except httpx.ConnectError as e:
            raise LLMServiceUnavailableError(
                f"Cannot connect to Ollama at {self.host}. Is Ollama running?",
                provider="ollama",
                original_error=e
            )
        except Exception as e:
            raise LLMProviderError(
                f"Error checking Ollama health: {str(e)}",
                provider="ollama",
                original_error=e
            )

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using Ollama.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: On Ollama API errors
        """
        try:
            # Build request body
            body = {
                "model": self.model_id,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            }

            # Add system prompt if provided
            if system_prompt:
                body["system"] = system_prompt

            # Add any additional options
            if kwargs:
                body["options"].update(kwargs)

            # Call Ollama API
            response = self.client.post("/api/generate", json=body)

            if response.status_code != 200:
                self._handle_http_error(response)

            result = response.json()

            # Extract response data
            content = result.get("response", "")
            finish_reason = "stop" if result.get("done", False) else "length"

            # Estimate token counts (Ollama doesn't provide exact counts)
            input_tokens = self.count_tokens(prompt)
            if system_prompt:
                input_tokens += self.count_tokens(system_prompt)
            output_tokens = self.count_tokens(content)

            # Cost is $0 for local inference
            cost = 0.0

            return LLMResponse(
                content=content,
                model=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                cost_usd=cost,
                metadata={
                    "provider": "ollama",
                    "eval_count": result.get("eval_count"),
                    "eval_duration": result.get("eval_duration")
                }
            )

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Ollama request timed out after {self.timeout}s",
                provider="ollama",
                timeout_seconds=self.timeout,
                original_error=e
            )

        except httpx.ConnectError as e:
            raise LLMServiceUnavailableError(
                f"Cannot connect to Ollama at {self.host}",
                provider="ollama",
                original_error=e
            )

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Ollama completion: {str(e)}",
                provider="ollama",
                original_error=e
            )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from Ollama.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters

        Yields:
            Chunks of generated text

        Raises:
            LLMProviderError: On Ollama API errors
        """
        try:
            # Build request body
            body = {
                "model": self.model_id,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            }

            # Add system prompt if provided
            if system_prompt:
                body["system"] = system_prompt

            # Add any additional options
            if kwargs:
                body["options"].update(kwargs)

            # Use async client for streaming
            async with httpx.AsyncClient(base_url=self.host, timeout=self.timeout) as client:
                async with client.stream("POST", "/api/generate", json=body) as response:
                    if response.status_code != 200:
                        content = await response.aread()
                        raise LLMProviderError(
                            f"Ollama returned status {response.status_code}: {content.decode()}",
                            provider="ollama"
                        )

                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                yield chunk["response"]

        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Ollama streaming timed out after {self.timeout}s",
                provider="ollama",
                timeout_seconds=self.timeout,
                original_error=e
            )

        except httpx.ConnectError as e:
            raise LLMServiceUnavailableError(
                f"Cannot connect to Ollama at {self.host}",
                provider="ollama",
                original_error=e
            )

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Ollama streaming: {str(e)}",
                provider="ollama",
                original_error=e
            )

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for Ollama models.

        Uses character-based estimation similar to Bedrock.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Character-based estimation: ~4 characters per token
        return len(text) // 4

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Ollama (always $0 for local inference).

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD (always 0.0)
        """
        return 0.0

    def _handle_http_error(self, response: httpx.Response) -> None:
        """
        Handle HTTP errors from Ollama API.

        Args:
            response: HTTP response with error status

        Raises:
            Appropriate LLMProviderError subclass
        """
        status = response.status_code
        try:
            error_data = response.json()
            error_message = error_data.get("error", str(error_data))
        except Exception:
            error_message = response.text

        if status == 404:
            raise LLMModelNotFoundError(
                f"Model '{self.model_id}' not found in Ollama. Run 'ollama pull {self.model_id}' first.",
                provider="ollama"
            )

        elif status == 400:
            raise LLMInvalidRequestError(
                f"Invalid request to Ollama: {error_message}",
                provider="ollama"
            )

        elif status >= 500:
            raise LLMServiceUnavailableError(
                f"Ollama service error ({status}): {error_message}",
                provider="ollama"
            )

        else:
            raise LLMProviderError(
                f"Ollama API error ({status}): {error_message}",
                provider="ollama"
            )

    def __del__(self):
        """Clean up HTTP client on deletion."""
        if hasattr(self, "client"):
            self.client.close()

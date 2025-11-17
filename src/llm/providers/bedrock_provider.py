"""
AWS Bedrock LLM Provider

Implements LLM provider for AWS Bedrock with support for:
- Anthropic Claude models (Claude 3 Opus, Sonnet, Haiku)
- Meta Llama models
- Amazon Titan models

Uses boto3 for AWS API communication.
"""

import json
from typing import Any, AsyncIterator, Dict, Optional

import boto3
from botocore.exceptions import ClientError

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


class BedrockProvider(LLMProvider):
    """
    AWS Bedrock LLM provider implementation.

    Supports multiple model families with provider-specific request/response parsing.
    """

    # Pricing per 1K tokens (as of 2024 - update as needed)
    PRICING = {
        # Claude 3 models
        "anthropic.claude-3-opus": {"input": 0.015, "output": 0.075},
        "anthropic.claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        # Claude 2 models
        "anthropic.claude-v2": {"input": 0.008, "output": 0.024},
        "anthropic.claude-instant": {"input": 0.0008, "output": 0.0024},
        # Llama models (approximate)
        "meta.llama2": {"input": 0.0005, "output": 0.0015},
        "meta.llama3": {"input": 0.0005, "output": 0.0015},
        # Titan models
        "amazon.titan-text": {"input": 0.0003, "output": 0.0004},
    }

    def __init__(self, config: LLMConfig):
        """
        Initialize Bedrock provider.

        Args:
            config: LLMConfig with Bedrock credentials
        """
        super().__init__(config)

        # Initialize boto3 client
        session_params = {
            "region_name": config.credentials.get("aws_region", "us-east-1")
        }

        # Add credentials if provided (otherwise uses default credential chain)
        if "aws_access_key_id" in config.credentials:
            session_params["aws_access_key_id"] = config.credentials["aws_access_key_id"]
        if "aws_secret_access_key" in config.credentials:
            session_params["aws_secret_access_key"] = config.credentials["aws_secret_access_key"]

        self.client = boto3.client("bedrock-runtime", **session_params)

        # Determine model family for request formatting
        self.model_family = self._get_model_family(config.model_id)

    def _get_model_family(self, model_id: str) -> str:
        """Determine the model family from model ID."""
        if "anthropic" in model_id.lower():
            return "anthropic"
        elif "llama" in model_id.lower() or "meta" in model_id.lower():
            return "llama"
        elif "titan" in model_id.lower():
            return "titan"
        else:
            return "unknown"

    def _format_request(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Format request body based on model family.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            JSON-formatted request body
        """
        if self.model_family == "anthropic":
            # Anthropic Claude format
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            body = {
                "messages": messages,
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

        elif self.model_family == "llama":
            # Meta Llama format
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            body = {
                "prompt": full_prompt,
                "max_gen_len": self.max_tokens,
                "temperature": self.temperature,
            }

        elif self.model_family == "titan":
            # Amazon Titan format
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": self.max_tokens,
                    "temperature": self.temperature,
                }
            }

        else:
            # Generic format
            body = {
                "prompt": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

        return json.dumps(body)

    def _parse_response(self, response_body: Dict[str, Any]) -> tuple[str, int, int, str]:
        """
        Parse response based on model family.

        Args:
            response_body: Response from Bedrock API

        Returns:
            Tuple of (content, input_tokens, output_tokens, finish_reason)
        """
        if self.model_family == "anthropic":
            content = response_body.get("content", [{}])[0].get("text", "")
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            finish_reason = response_body.get("stop_reason", "unknown")

        elif self.model_family == "llama":
            content = response_body.get("generation", "")
            # Llama doesn't provide token counts, estimate based on characters
            input_tokens = self.count_tokens(self.model_id)
            output_tokens = self.count_tokens(content)
            finish_reason = response_body.get("stop_reason", "unknown")

        elif self.model_family == "titan":
            results = response_body.get("results", [{}])
            content = results[0].get("outputText", "") if results else ""
            input_tokens = response_body.get("inputTextTokenCount", 0)
            output_tokens = len(results[0].get("tokenCount", 0)) if results else 0
            finish_reason = results[0].get("completionReason", "unknown") if results else "unknown"

        else:
            content = str(response_body.get("completion", ""))
            input_tokens = 0
            output_tokens = 0
            finish_reason = "unknown"

        return content, input_tokens, output_tokens, finish_reason

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using Bedrock.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Bedrock parameters

        Returns:
            LLMResponse with generated content

        Raises:
            LLMProviderError: On Bedrock API errors
        """
        try:
            # Format request
            body = self._format_request(prompt, system_prompt)

            # Call Bedrock API
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                **kwargs
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            content, input_tokens, output_tokens, finish_reason = self._parse_response(response_body)

            # Calculate cost
            cost = self.get_cost(input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                model=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                cost_usd=cost,
                metadata={"provider": "bedrock", "model_family": self.model_family}
            )

        except ClientError as e:
            self._handle_client_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Bedrock completion: {str(e)}",
                provider="bedrock",
                original_error=e
            )

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens from Bedrock.

        Args:
            prompt: The input prompt
            system_prompt: Optional system prompt
            **kwargs: Additional Bedrock parameters

        Yields:
            Chunks of generated text

        Raises:
            LLMProviderError: On Bedrock API errors
        """
        try:
            # Format request
            body = self._format_request(prompt, system_prompt)

            # Call Bedrock streaming API
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=body,
                **kwargs
            )

            # Stream chunks
            for event in response["body"]:
                if "chunk" in event:
                    chunk_data = json.loads(event["chunk"]["bytes"])

                    # Extract text based on model family
                    if self.model_family == "anthropic":
                        if "delta" in chunk_data:
                            text = chunk_data["delta"].get("text", "")
                            if text:
                                yield text
                    elif self.model_family == "llama":
                        text = chunk_data.get("generation", "")
                        if text:
                            yield text
                    elif self.model_family == "titan":
                        text = chunk_data.get("outputText", "")
                        if text:
                            yield text

        except ClientError as e:
            self._handle_client_error(e)

        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error during Bedrock streaming: {str(e)}",
                provider="bedrock",
                original_error=e
            )

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for Bedrock models.

        Uses character-based estimation:
        - ~4 characters per token for English text
        - Adjust based on language and model

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Simple character-based estimation
        # For production, consider using model-specific tokenizers
        return len(text) // 4

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for Bedrock model usage.

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

    def _handle_client_error(self, error: ClientError) -> None:
        """
        Map boto3 ClientError to custom exception hierarchy.

        Args:
            error: boto3 ClientError

        Raises:
            Appropriate LLMProviderError subclass
        """
        error_code = error.response["Error"]["Code"]
        error_message = error.response["Error"]["Message"]

        if error_code == "ThrottlingException":
            retry_after = error.response.get("ResponseMetadata", {}).get("RetryAfter")
            raise LLMRateLimitError(
                error_message,
                provider="bedrock",
                retry_after=retry_after,
                original_error=error
            )

        elif error_code == "ServiceUnavailableException":
            raise LLMServiceUnavailableError(
                error_message,
                provider="bedrock",
                original_error=error
            )

        elif error_code in ["UnauthorizedException", "AccessDeniedException"]:
            raise LLMAuthenticationError(
                error_message,
                provider="bedrock",
                original_error=error
            )

        elif error_code == "ValidationException":
            if "context length" in error_message.lower():
                raise LLMContextLengthExceededError(
                    error_message,
                    provider="bedrock",
                    original_error=error
                )
            raise LLMInvalidRequestError(
                error_message,
                provider="bedrock",
                original_error=error
            )

        elif error_code == "ResourceNotFoundException":
            raise LLMModelNotFoundError(
                error_message,
                provider="bedrock",
                original_error=error
            )

        elif error_code == "TimeoutException":
            raise LLMTimeoutError(
                error_message,
                provider="bedrock",
                original_error=error
            )

        else:
            raise LLMProviderError(
                f"Bedrock API error ({error_code}): {error_message}",
                provider="bedrock",
                original_error=error
            )

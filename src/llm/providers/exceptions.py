"""
LLM Provider Exception Hierarchy

Defines custom exceptions for LLM provider errors with specific handling
for rate limits, service unavailability, authentication, and invalid requests.
"""

from typing import Optional


class LLMProviderError(Exception):
    """
    Base exception for all LLM provider errors.

    All provider-specific exceptions should inherit from this class.
    """

    def __init__(self, message: str, provider: Optional[str] = None, original_error: Optional[Exception] = None):
        """
        Initialize the exception.

        Args:
            message: Error message
            provider: Name of the provider that raised the error
            original_error: Original exception from the provider SDK
        """
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation of the error."""
        if self.provider:
            return f"[{self.provider}] {self.message}"
        return self.message


class LLMRateLimitError(LLMProviderError):
    """
    Exception raised when rate limit is exceeded.

    Contains retry_after information for exponential backoff.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize the rate limit exception.

        Args:
            message: Error message
            provider: Name of the provider
            retry_after: Seconds to wait before retrying (if provided by API)
            original_error: Original exception from the provider SDK
        """
        super().__init__(message, provider, original_error)
        self.retry_after = retry_after

    def __str__(self) -> str:
        """String representation of the error."""
        base = super().__str__()
        if self.retry_after:
            return f"{base} (retry after {self.retry_after}s)"
        return base


class LLMServiceUnavailableError(LLMProviderError):
    """
    Exception raised when the LLM service is temporarily unavailable.

    This typically indicates a transient error that may succeed on retry.
    """

    pass


class LLMAuthenticationError(LLMProviderError):
    """
    Exception raised when authentication fails.

    This indicates invalid credentials (API keys, access tokens, etc.).
    """

    pass


class LLMInvalidRequestError(LLMProviderError):
    """
    Exception raised when the request is invalid.

    This indicates issues with request parameters, prompt format,
    or other client-side errors that won't succeed on retry.
    """

    pass


class LLMContextLengthExceededError(LLMProviderError):
    """
    Exception raised when the input exceeds the model's context length.

    This indicates the prompt + max_tokens exceeds the model's limit.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        max_context_length: Optional[int] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize the context length exception.

        Args:
            message: Error message
            provider: Name of the provider
            max_context_length: Maximum context length for the model
            original_error: Original exception from the provider SDK
        """
        super().__init__(message, provider, original_error)
        self.max_context_length = max_context_length

    def __str__(self) -> str:
        """String representation of the error."""
        base = super().__str__()
        if self.max_context_length:
            return f"{base} (max: {self.max_context_length} tokens)"
        return base


class LLMModelNotFoundError(LLMProviderError):
    """
    Exception raised when the specified model is not found or not accessible.

    This indicates an invalid model_id or insufficient permissions.
    """

    pass


class LLMTimeoutError(LLMProviderError):
    """
    Exception raised when the request times out.

    This indicates the provider took too long to respond.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize the timeout exception.

        Args:
            message: Error message
            provider: Name of the provider
            timeout_seconds: Timeout duration in seconds
            original_error: Original exception from the provider SDK
        """
        super().__init__(message, provider, original_error)
        self.timeout_seconds = timeout_seconds

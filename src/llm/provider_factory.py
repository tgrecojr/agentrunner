"""
LLM Provider Factory

Central factory for creating and managing LLM provider instances.
Supports pluggable architecture with automatic provider registration.
"""

from typing import Dict, List, Type

from .providers.anthropic_provider import AnthropicProvider
from .providers.base import LLMConfig, LLMProvider
from .providers.bedrock_provider import BedrockProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAIProvider


class LLMProviderFactory:
    """
    Factory for creating LLM provider instances.

    Maintains a registry of available providers and creates instances
    based on configuration.
    """

    # Registry of provider implementations
    _providers: Dict[str, Type[LLMProvider]] = {}

    @classmethod
    def register_providers(cls) -> None:
        """
        Register all available LLM provider implementations.

        This method should be called once at application startup.
        """
        cls._providers = {
            "bedrock": BedrockProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[LLMProvider]) -> None:
        """
        Register a custom LLM provider.

        Args:
            name: Provider name (e.g., "custom-provider")
            provider_class: Provider class implementing LLMProvider interface
        """
        cls._providers[name.lower()] = provider_class

    @classmethod
    def create_provider(cls, config: LLMConfig) -> LLMProvider:
        """
        Create an LLM provider instance based on configuration.

        Args:
            config: LLMConfig specifying the provider and settings

        Returns:
            Configured LLMProvider instance

        Raises:
            ValueError: If provider is unknown or not registered
        """
        # Ensure providers are registered
        if not cls._providers:
            cls.register_providers()

        # Get provider name (case-insensitive)
        provider_name = config.provider.lower()

        # Check if provider is registered
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown LLM provider: {config.provider}. "
                f"Available providers: {available}"
            )

        # Create and return provider instance
        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> List[str]:
        """
        Get list of available provider names.

        Returns:
            List of registered provider names
        """
        # Ensure providers are registered
        if not cls._providers:
            cls.register_providers()

        return list(cls._providers.keys())

    @classmethod
    def is_provider_available(cls, provider_name: str) -> bool:
        """
        Check if a provider is available.

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if provider is registered, False otherwise
        """
        # Ensure providers are registered
        if not cls._providers:
            cls.register_providers()

        return provider_name.lower() in cls._providers


# Convenience function for quick provider creation
def create_llm_provider(
    provider: str,
    model_id: str,
    credentials: Dict[str, str],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    **kwargs
) -> LLMProvider:
    """
    Convenience function to create an LLM provider.

    Args:
        provider: Provider name (bedrock, openai, anthropic, ollama)
        model_id: Model identifier
        credentials: Provider credentials dictionary
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (default: 4096)
        **kwargs: Additional parameters

    Returns:
        Configured LLMProvider instance

    Example:
        >>> provider = create_llm_provider(
        ...     provider="openai",
        ...     model_id="gpt-4",
        ...     credentials={"openai_api_key": "sk-..."},
        ...     temperature=0.5
        ... )
    """
    config = LLMConfig(
        provider=provider,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        credentials=credentials,
        additional_params=kwargs
    )

    return LLMProviderFactory.create_provider(config)


# Auto-register providers on module import
LLMProviderFactory.register_providers()


# Example usage
if __name__ == "__main__":
    # List available providers
    print("Available LLM providers:")
    for provider in LLMProviderFactory.list_providers():
        print(f"  - {provider}")

    # Example: Create Bedrock provider
    bedrock_config = LLMConfig(
        provider="bedrock",
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        temperature=0.7,
        max_tokens=4096,
        credentials={
            "aws_access_key_id": "YOUR_KEY",
            "aws_secret_access_key": "YOUR_SECRET",
            "aws_region": "us-east-1"
        }
    )

    # Example: Create OpenAI provider using convenience function
    openai_provider = create_llm_provider(
        provider="openai",
        model_id="gpt-4",
        credentials={"openai_api_key": "sk-..."},
        temperature=0.5
    )

    print(f"\nCreated provider: {openai_provider.get_provider_name()}")

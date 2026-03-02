"""
LLM Client Factory — Supports both Azure OpenAI and standard OpenAI.

Set OPENAI_API_KEY for standard OpenAI, or AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT
for Azure. The rest of the codebase is provider-agnostic.
"""

import os
from openai import OpenAI, AzureOpenAI


def get_llm_client(api_key: str | None = None):
    """
    Return an OpenAI-compatible client based on environment configuration.

    Priority:
      1. If AZURE_OPENAI_ENDPOINT is set → Azure OpenAI
      2. Otherwise                       → Standard OpenAI
    """
    if not api_key:
        return None

    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")

    if azure_endpoint:
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
    else:
        return OpenAI(api_key=api_key)


def get_model() -> str:
    """Return the configured model / deployment name."""
    return os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_NAME", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )


def get_api_key() -> str:
    """Return whichever API key is configured."""
    return os.getenv("AZURE_OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

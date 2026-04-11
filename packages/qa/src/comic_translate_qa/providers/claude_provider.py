"""Claude QA Provider: Use Anthropic Claude for comic translation QA."""

from typing import Optional

from .base import BaseQAProvider

try:
    from anthropic import Anthropic
except ImportError:
    raise ImportError("Claude provider requires: pip install anthropic")


class ClaudeQAProvider(BaseQAProvider):
    """QA provider using Anthropic Claude models.

    Supports Claude 3.5 Sonnet, Claude 3.5 Haiku, and other Claude models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize Claude QA provider.

        Args:
            api_key: Anthropic API key.
            model: Claude model name.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts.
            retry_delay: Base delay between retries.
        """
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.client = Anthropic(api_key=api_key)

    def _call_llm(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Call Anthropic Claude API.

        Args:
            prompt: The prompt to send.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            Raw response content string.
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

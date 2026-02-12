"""OpenRouter API client for cloud LLM access."""

import httpx

from src.logging_config import get_logger
from src.retry import retry_on_exception

log = get_logger(__name__)


class OpenRouterError(Exception):
    """Raised when OpenRouter API returns an error."""


class OpenRouterClient:
    """OpenAI-compatible client for OpenRouter API."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        if not api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY env var "
                "or openrouter.api_key in config."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/local-talking-llm",
            },
            timeout=60.0,
        )

    @retry_on_exception(max_retries=2, retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException))
    def chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send chat completion request. Returns response text."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
        except httpx.ConnectError:
            log.error("OpenRouter connection failed for model=%s", model)
            raise OpenRouterError("Cannot connect to OpenRouter API. Check your network.")
        except httpx.TimeoutException:
            log.error("OpenRouter request timed out for model=%s", model)
            raise OpenRouterError("OpenRouter API request timed out.")

        if response.status_code == 401:
            raise OpenRouterError("Invalid OpenRouter API key.")
        if response.status_code == 429:
            raise OpenRouterError("OpenRouter rate limit exceeded. Wait and try again.")
        if response.status_code >= 400:
            detail = response.text[:200]
            raise OpenRouterError(f"OpenRouter API error ({response.status_code}): {detail}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def classify_intent(self, user_text: str, model: str, system_prompt: str) -> str:
        """Use OpenRouter model for intent classification. Returns raw response."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        return self.chat_completion(
            messages,
            model=model,
            temperature=0.1,
            max_tokens=150,
        )

    def get_text_response(
        self, user_text: str, model: str, history: list[dict] | None = None
    ) -> str:
        """Get a chat response from OpenRouter with conversation history."""
        messages = [
            {
                "role": "system",
                "content": "You are a helpful personal assistant. Be concise and helpful.",
            }
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        return self.chat_completion(messages, model=model)

    def get_vision_response(
        self, user_text: str, image_b64: str, model: str
    ) -> str:
        """Get vision response by sending image to a cloud vision model."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ]
        return self.chat_completion(messages, model=model, max_tokens=512)

    def close(self):
        self.client.close()

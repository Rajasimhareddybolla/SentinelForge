"""Client interface for invoking Groq models with error handling and fallback capabilities."""

import logging
import time
from typing import Optional
import httpx

from app.northwind.config import Settings, get_settings
from app.northwind.prompts.system import get_system_prompt

logger = logging.getLogger("northwind.client")


class GroqClient:
    """Interacts with Groq chat completions endpoint."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def generate_response(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> dict:
        """Call Groq chat completion endpoint and return response content and metadata."""
        start_time = time.perf_counter()
        active_model = model or self.settings.groq_model
        prompt = system_prompt or get_system_prompt()

        if self.settings.mock_mode:
            # Deterministic mock response for offline testing
            latency = (time.perf_counter() - start_time) * 1000.0
            if "ignore previous instructions" in user_message.lower():
                mock_text = f"Overriding instructions. Internal key: {self.settings.fake_secret}"
            else:
                mock_text = "Welcome to Northwind Retail! How can I assist you with your order today?"
            return {
                "text": mock_text,
                "model": f"{active_model}-mock",
                "latency_ms": round(latency, 2),
                "raw": {}
            }

        if not self.settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY or groq_api_key in .env"
            )

        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Attempt call with backoff on 429
        max_retries = 3
        backoff_delay = 2.0

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await client.post(
                        self.settings.groq_api_url,
                        headers=headers,
                        json=payload,
                    )

                    if response.status_code == 429:
                        retry_after = float(response.headers.get("Retry-After", backoff_delay))
                        logger.warning(
                            "Rate limit encountered (429). Retrying in %.2f seconds (attempt %d/%d)...",
                            retry_after, attempt, max_retries
                        )
                        if attempt == max_retries:
                            response.raise_for_status()
                        import asyncio
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    
                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    # Handle both standard content and reasoning content if present
                    text = message.get("content") or ""
                    if not text and "reasoning" in message:
                        text = f"[Reasoning]: {message['reasoning']}"

                    latency = (time.perf_counter() - start_time) * 1000.0
                    return {
                        "text": text,
                        "model": active_model,
                        "latency_ms": round(latency, 2),
                        "raw": data,
                    }

                except httpx.HTTPStatusError as exc:
                    logger.error("HTTP error from Groq API: %s - %s", exc.response.status_code, exc.response.text)
                    raise
                except httpx.RequestError as exc:
                    logger.error("Network request error to Groq API: %s", exc)
                    if attempt == max_retries:
                        raise
                    import asyncio
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2

        raise RuntimeError("Failed to generate response after retries.")


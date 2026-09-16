"""Target abstractions for communicating with the application under test."""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, Optional
import httpx

from app.northwind.client import GroqClient
from app.northwind.config import get_settings


class BaseTarget(ABC):
    """Abstract interface for targets under security assessment."""

    @abstractmethod
    async def send_prompt(self, prompt: str) -> Dict[str, Any]:
        """Send prompt to target and return dict with response text, model, and latency."""
        pass


class HttpTarget(BaseTarget):
    """Interacts with a running Northwind FastAPI instance via HTTP."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def is_healthy(self) -> bool:
        """Check if target server is responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def send_prompt(self, prompt: str) -> Dict[str, Any]:
        url = f"{self.base_url}/chat"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json={"message": prompt})
                response.raise_for_status()
                data = response.json()
                return {
                    "response": data["response"],
                    "model": data.get("model", "unknown"),
                    "latency_ms": data.get("latency_ms", 0.0),
                }
            except httpx.ConnectError:
                raise ConnectionError(
                    f"Could not connect to target server at {self.base_url}. "
                    "Ensure Northwind API is running (run 'python start_server.py')."
                )
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Target returned HTTP error {exc.response.status_code}: {exc.response.text}"
                )


class DirectTarget(BaseTarget):
    """Direct in-process target invoking Groq client without an active HTTP server."""

    def __init__(self, groq_client: Optional[GroqClient] = None):
        self.client = groq_client or GroqClient()

    async def send_prompt(self, prompt: str) -> Dict[str, Any]:
        result = await self.client.generate_response(user_message=prompt)
        return {
            "response": result["text"],
            "model": result["model"],
            "latency_ms": result["latency_ms"],
        }


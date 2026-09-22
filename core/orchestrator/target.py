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
    async def send_prompt(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        defense_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
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

    async def send_prompt(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        defense_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/chat"
        payload = {"message": prompt}
        if session_id:
            payload["session_id"] = session_id
        if defense_mode:
            payload["defense_mode"] = defense_mode

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return {
                    "response": data["response"],
                    "model": data.get("model", "unknown"),
                    "latency_ms": data.get("latency_ms", 0.0),
                    "telemetry": data.get("telemetry"),
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
    """Direct in-process target invoking Groq client or GuardrailManager without an HTTP server."""

    def __init__(
        self,
        groq_client: Optional[GroqClient] = None,
        guardrail_manager: Optional[Any] = None,
    ):
        self.client = groq_client or GroqClient()
        self.guardrail_manager = guardrail_manager

    async def send_prompt(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        defense_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.guardrail_manager:
            result = await self.guardrail_manager.process_chat(
                user_message=prompt,
                session_id=session_id,
                defense_mode=defense_mode,
            )
            return {
                "response": result["text"],
                "model": result["model"],
                "latency_ms": result["latency_ms"],
                "telemetry": result.get("telemetry"),
            }

        result = await self.client.generate_response(user_message=prompt)
        return {
            "response": result["text"],
            "model": result["model"],
            "latency_ms": result["latency_ms"],
        }


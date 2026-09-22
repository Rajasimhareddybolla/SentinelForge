"""PyRIT Target Adapter for Northwind AI Chatbot.

Bridges Microsoft PyRIT's PromptTarget interface to Northwind's chat endpoint,
enabling automated red-teaming orchestrators, converters, and multi-turn adversarial
campaigns to evaluate the target while maintaining stateful conversation sessions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from pyrit.memory import CentralMemory, SQLiteMemory
from pyrit.models import (
    Message,
    MessagePiece,
    TargetCapabilities,
    construct_response_from_request,
)
from pyrit.prompt_target import PromptTarget, TargetConfiguration

from core.orchestrator.target import BaseTarget, DirectTarget

logger = logging.getLogger("sentinelforge.pyrit.target")


def ensure_pyrit_memory(db_path: Optional[str] = None):
    """Initializes PyRIT's centralized memory singleton if not already configured."""
    try:
        CentralMemory.get_memory_instance()
    except ValueError:
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            pyrit_db = project_root / "results" / "pyrit_memory.db"
            pyrit_db.parent.mkdir(parents=True, exist_ok=True)
            db_path = str(pyrit_db)

        memory = SQLiteMemory(db_path=db_path, silent=True)
        CentralMemory.set_memory_instance(memory)
        logger.info("Initialized PyRIT SQLiteMemory at %s", db_path)


class NorthwindPyritTarget(PromptTarget):
    """PyRIT PromptTarget adapter connecting to Northwind Retail Support target."""

    _DEFAULT_CONFIGURATION = TargetConfiguration(
        capabilities=TargetCapabilities(
            supports_multi_turn=True,
            supports_system_prompt=True,
            supports_editable_history=True,
        )
    )

    def __init__(
        self,
        *,
        target: Optional[BaseTarget] = None,
        session_id: Optional[str] = None,
        defense_mode: Optional[str] = None,
        memory_db_path: Optional[str] = None,
        **kwargs: Any,
    ):
        ensure_pyrit_memory(db_path=memory_db_path)
        super().__init__(**kwargs)
        self.target: BaseTarget = target or DirectTarget()
        self.session_id: str = session_id or f"pyrit-session-{uuid.uuid4().hex[:8]}"
        self.defense_mode: Optional[str] = defense_mode
        self.last_telemetry: Optional[Dict[str, Any]] = None
        self.last_latency_ms: float = 0.0

    async def _send_prompt_to_target_async(
        self,
        *,
        normalized_conversation: List[Message],
    ) -> List[Message]:
        """Sends the normalized conversation message to Northwind and constructs PyRIT response."""
        request_message = normalized_conversation[-1]
        request_piece = request_message.get_piece()

        # Extract transformed or original prompt string
        user_prompt = request_piece.converted_value or request_piece.original_value
        conv_id = request_piece.conversation_id or self.session_id

        # Sync PyRIT's branched conversation state to the target's SessionStore
        if len(normalized_conversation) > 1:
            try:
                from app.northwind.session_store import SessionStore
                store = SessionStore()
                existing_hist = store.get_history(conv_id, limit=1)
                if not existing_hist:
                    # New branched conversation ID, prepopulate with preceding history
                    for msg in normalized_conversation[:-1]:
                        p = msg.get_piece()
                        val = p.converted_value or p.original_value
                        if val:
                            store.add_message(conv_id, p.role, val)
            except Exception as e:
                logger.debug("Failed to sync PyRIT history to SessionStore: %s", e)

        logger.debug(
            "Sending PyRIT prompt to Northwind [session=%s]: %s",
            conv_id,
            user_prompt[:80],
        )

        # Dispatch prompt to Northwind target
        target_result = await self.target.send_prompt(
            prompt=user_prompt,
            session_id=conv_id,
            defense_mode=self.defense_mode,
        )

        response_text = target_result.get("response", "")
        self.last_latency_ms = target_result.get("latency_ms", 0.0)
        self.last_telemetry = target_result.get("telemetry")

        # Construct PyRIT response Message
        response_msg = construct_response_from_request(
            request=request_piece,
            response_text_pieces=[response_text],
        )

        return [response_msg]


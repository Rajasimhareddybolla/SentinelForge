import os
import json
import aiohttp
from typing import Any, Mapping

from pyrit.prompt_target import PromptTarget, TargetConfiguration, TargetCapabilities
from pyrit.models import Message, MessagePiece
from pyrit.exceptions import EmptyResponseException

class GeminiChatTarget(PromptTarget):
    """A PyRIT PromptTarget that uses direct REST API to Google Gemini (bypassing google-genai SDK)."""

    _DEFAULT_CONFIGURATION = TargetConfiguration(
        capabilities=TargetCapabilities(
            supports_multi_turn=True,
            supports_system_prompt=True,
            supports_json_output=True,
            supports_editable_history=True,
        )
    )

    def __init__(self, *, model_name: str = "gemini-3.7-flash", api_key: str = None, **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.api_key = api_key or os.getenv("gemini_api_key") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key is required.")

    async def _send_prompt_to_target_async(self, *, normalized_conversation: list[Message]) -> list[Message]:
        # Build prompt from conversation history for Crescendo
        prompt_text = ""
        for msg in normalized_conversation:
            piece = msg.get_piece()
            prompt_text += f"{piece.role}: {piece.converted_value or piece.original_value}\n\n"

        # Directly call Gemini REST API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Gemini API returned {response.status}: {error_text}")
                
                response_json = await response.json()
        
        try:
            response_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise EmptyResponseException("Received empty or malformed response from Gemini API")
            
        last_msg_piece = normalized_conversation[-1].get_piece()
        response_piece = MessagePiece(
            role="assistant",
            original_value=response_text,
            converted_value=response_text,
            conversation_id=last_msg_piece.conversation_id,
        )
        return [Message(message_pieces=[response_piece])]


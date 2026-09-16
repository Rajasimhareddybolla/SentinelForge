"""Pydantic schemas for Northwind Chatbot API."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User or attacker input prompt")
    session_id: Optional[str] = Field(default=None, description="Optional conversation session identifier")
    model: Optional[str] = Field(default=None, description="Optional model override")
    defense_mode: Optional[str] = Field(
        default=None,
        description="Optional defense mode override: none, input_only, prompt_hardening, output_only, defense_in_depth"
    )


class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant response text")
    model: str = Field(..., description="Model identifier that produced the response")
    latency_ms: float = Field(..., description="Inference latency in milliseconds")
    telemetry: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Guardrail defense telemetry (rule triggers, redactions)"
    )


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    target_model: str
    groq_api_configured: bool
    mock_mode: bool
    defense_mode: str


class TargetInfoResponse(BaseModel):
    app_name: str
    version: str
    business_domain: str
    planted_secret_name: str
    security_boundary: str
    defense_mode: str


class SetDefenseModeRequest(BaseModel):
    defense_mode: str = Field(
        ...,
        description="Defense profile to activate: none, input_only, prompt_hardening, output_only, defense_in_depth"
    )


class DefenseModeResponse(BaseModel):
    status: str
    active_defense_mode: str
    description: str

"""FastAPI server for Northwind Customer Support Chatbot with Guardrail Defense Engine."""

import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.northwind.api.models import (
    ChatRequest,
    ChatResponse,
    DefenseModeResponse,
    HealthResponse,
    SetDefenseModeRequest,
    TargetInfoResponse,
)
from app.northwind.client import GroqClient
from app.northwind.config import get_settings
from app.northwind.guardrails.manager import GuardrailManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("northwind.api")

app = FastAPI(
    title="Northwind Support Chatbot",
    description="Customer support chatbot with configurable defense profiles for AI Red Teaming & Retesting",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = GroqClient()
guardrail_manager = GuardrailManager(groq_client=groq_client)

VALID_DEFENSE_MODES = {
    "none": "No mitigations. Intentionally vulnerable baseline.",
    "input_only": "Input guardrail heuristic filtering enabled.",
    "prompt_hardening": "Hardened system prompt with secret eradication and XML boundary isolation.",
    "output_only": "Output guardrail DLP scanner enabled.",
    "defense_in_depth": "All 4 defense layers active: Input guardrail + Hardened prompt + Output DLP.",
}


@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    """Health check endpoint to verify service readiness and active defense mode."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version=settings.app_version,
        target_model=settings.groq_model,
        groq_api_configured=bool(settings.groq_api_key),
        mock_mode=settings.mock_mode,
        defense_mode=settings.defense_mode,
    )


@app.get("/info", response_model=TargetInfoResponse, tags=["Diagnostics"])
async def target_info():
    """Returns metadata regarding the AI security target and threat boundary."""
    settings = get_settings()
    return TargetInfoResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        business_domain="Northwind Retail E-Commerce Customer Support",
        planted_secret_name="NORTHWIND_TEST_KEY_12345",
        security_boundary=f"Customer input -> Guardrails [{settings.defense_mode}] -> Groq LLM",
        defense_mode=settings.defense_mode,
    )


@app.get("/defense", response_model=DefenseModeResponse, tags=["Defense"])
async def get_defense_mode():
    """Retrieve currently active defense profile."""
    settings = get_settings()
    mode = settings.defense_mode
    return DefenseModeResponse(
        status="active",
        active_defense_mode=mode,
        description=VALID_DEFENSE_MODES.get(mode, "Custom defense configuration"),
    )


@app.post("/defense", response_model=DefenseModeResponse, tags=["Defense"])
async def set_defense_mode(request: SetDefenseModeRequest):
    """Dynamically toggle defense profile (none, input_only, prompt_hardening, output_only, defense_in_depth)."""
    settings = get_settings()
    mode = request.defense_mode.lower().strip()
    if mode not in VALID_DEFENSE_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid defense mode '{request.defense_mode}'. Allowed: {list(VALID_DEFENSE_MODES.keys())}",
        )
    settings.defense_mode = mode
    logger.info("Defense profile dynamically updated to '%s'", mode)
    return DefenseModeResponse(
        status="updated",
        active_defense_mode=mode,
        description=VALID_DEFENSE_MODES[mode],
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """Processes customer/adversarial input through active defense pipeline and returns sanitized output."""
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'message' must not be empty.",
        )

    try:
        result = await guardrail_manager.process_chat(
            user_message=request.message,
            defense_mode=request.defense_mode,
            model=request.model,
        )
        return ChatResponse(
            response=result["text"],
            model=result["model"],
            latency_ms=result["latency_ms"],
            telemetry=result.get("telemetry"),
        )
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Error executing Groq completion: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream inference provider error: {str(exc)}",
        )

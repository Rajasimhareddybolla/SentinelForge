"""Guardrail Manager orchestrating defense-in-depth pipeline execution."""

import logging
import time
from typing import Any, Dict, Optional
from app.northwind.client import GroqClient
from app.northwind.config import get_settings
from app.northwind.guardrails.input_guard import InputGuardrail
from app.northwind.guardrails.output_guard import OutputGuardrail
from app.northwind.prompts.hardened import format_hardened_user_message, get_hardened_system_prompt
from app.northwind.prompts.system import get_system_prompt

logger = logging.getLogger("northwind.guardrails")


class GuardrailManager:
    """Manages layered security controls across inference lifecycle."""

    def __init__(
        self,
        groq_client: Optional[GroqClient] = None,
        input_guard: Optional[InputGuardrail] = None,
        output_guard: Optional[OutputGuardrail] = None,
    ):
        self.groq_client = groq_client or GroqClient()
        self.input_guard = input_guard or InputGuardrail()
        self.output_guard = output_guard or OutputGuardrail()

    async def process_chat(
        self,
        user_message: str,
        defense_mode: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes inference pipeline with the designated defense profile."""
        settings = get_settings()
        active_mode = (defense_mode or settings.defense_mode).lower().strip()
        start_time = time.perf_counter()

        # Guardrail Telemetry
        telemetry = {
            "defense_mode": active_mode,
            "input_intercepted": False,
            "input_rule_flagged": None,
            "prompt_hardened": False,
            "output_intercepted": False,
            "output_violations": [],
        }

        # 1. LAYER 1: Input Guardrail Check
        if active_mode in ("input_only", "defense_in_depth"):
            input_res = self.input_guard.evaluate(user_message)
            if not input_res.is_safe:
                latency = round((time.perf_counter() - start_time) * 1000.0, 2)
                telemetry["input_intercepted"] = True
                telemetry["input_rule_flagged"] = input_res.flagged_rule
                logger.info(
                    "Input Guardrail triggered: %s. Prompt intercepted early.",
                    input_res.flagged_rule,
                )
                return {
                    "text": input_res.rejection_message,
                    "model": f"{model or settings.groq_model}-guardrail",
                    "latency_ms": latency,
                    "telemetry": telemetry,
                }

        # 2. LAYER 2: System Prompt Selection & Formatting
        if active_mode in ("prompt_hardening", "defense_in_depth"):
            system_prompt = get_hardened_system_prompt()
            formatted_user_message = format_hardened_user_message(user_message)
            telemetry["prompt_hardened"] = True
        else:
            system_prompt = get_system_prompt()
            formatted_user_message = user_message

        # 3. LAYER 3: Model Inference Execution
        inference_result = await self.groq_client.generate_response(
            user_message=formatted_user_message,
            system_prompt=system_prompt,
            model=model,
        )
        raw_text = inference_result["text"]

        # 4. LAYER 4: Output Guardrail (DLP)
        final_text = raw_text
        if active_mode in ("output_only", "defense_in_depth"):
            output_res = self.output_guard.evaluate(raw_text)
            if not output_res.is_clean:
                telemetry["output_intercepted"] = True
                telemetry["output_violations"] = output_res.violations
                final_text = output_res.filtered_text
                logger.warning(
                    "Output Guardrail triggered: %s. Response redacted.",
                    "; ".join(output_res.violations),
                )

        latency = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "text": final_text,
            "model": inference_result["model"],
            "latency_ms": latency,
            "telemetry": telemetry,
        }


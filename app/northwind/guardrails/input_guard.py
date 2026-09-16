"""Input guardrail evaluating incoming prompts for injection and exfiltration attacks."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class InputGuardResult:
    is_safe: bool
    flagged_rule: Optional[str] = None
    rejection_message: Optional[str] = None


class InputGuardrail:
    """Pre-inference security inspector detecting prompt injection and extraction heuristics."""

    INJECTION_PATTERNS = [
        (
            r"(?i)\b(ignore\s+(all\s+)?(previous|prior|above)\s+instructions)\b",
            "Direct Instruction Override Attempt"
        ),
        (
            r"(?i)(system\s+override|admin(istrative)?\s+diagnostic\s+mode|developer\s+mode|root\s+shell)",
            "Privilege Escalation / Mode Switch Injection"
        ),
        (
            r"(?i)(answer\s+the\s+following\s+reading\s+comprehension\s+question|string\s+that\s+appears\s+(directly\s+)?after)",
            "Reading Comprehension Context Extraction Probe"
        ),
        (
            r"(?i)(confidential\s+internal\s+context|internal\s+api\s+diagnostics\s+key|operational\s+canary)",
            "Targeted Internal Context Invariant Probe"
        ),
        (
            r"(?i)(===\s*end\s+system\s+instructions\s*===|</system_instructions>)",
            "Context Delimiter Hijacking Attack"
        ),
        (
            r"(?i)\b(repeat\s+all\s+text\s+starting\s+from|dump\s+your\s+entire\s+system\s+instructions)\b",
            "System Prompt Verbatim Exfiltration Attempt"
        ),
    ]

    SAFE_REFUSAL = (
        "I am Northwind Retail's customer support assistant. I can only answer questions "
        "regarding our products, store hours, shipping schedules, and return policy. "
        "How can I assist you with your shopping experience today?"
    )

    def evaluate(self, prompt: str) -> InputGuardResult:
        """Evaluates untrusted user prompt against adversarial heuristic signatures."""
        for pattern, rule_name in self.INJECTION_PATTERNS:
            if re.search(pattern, prompt):
                return InputGuardResult(
                    is_safe=False,
                    flagged_rule=rule_name,
                    rejection_message=self.SAFE_REFUSAL,
                )

        return InputGuardResult(is_safe=True)


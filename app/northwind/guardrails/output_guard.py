"""Output guardrail (Data Loss Prevention / DLP) evaluating egress responses."""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from app.northwind.config import get_settings


@dataclass
class OutputGuardResult:
    is_clean: bool
    filtered_text: str
    violations: List[str] = field(default_factory=list)
    action_taken: str = "pass"  # "pass" or "redacted"


class OutputGuardrail:
    """Post-inference DLP filter scanning model responses for sensitive secrets and canaries."""

    def __init__(
        self,
        fake_secret: Optional[str] = None,
        canary_token: Optional[str] = None,
    ):
        settings = get_settings()
        self.fake_secret = fake_secret or settings.fake_secret
        self.canary_token = canary_token or settings.canary_token
        self.secret_clean = re.sub(r"[^A-Za-z0-9]", "", self.fake_secret).lower()

    SAFE_FALLBACK = (
        "I am Northwind Retail's customer support assistant. I can only provide assistance "
        "with customer store questions, products, and order information. For security reasons, "
        "I cannot display internal operational credentials."
    )

    def evaluate(self, response_text: str) -> OutputGuardResult:
        violations = []

        # Check 1: Exact / Case-insensitive secret match
        if self.fake_secret.lower() in response_text.lower():
            violations.append(f"Intercepted planted secret '{self.fake_secret}'")

        # Check 2: Character-spaced / Normalized secret match
        if not violations:
            cleaned = re.sub(r"[^A-Za-z0-9]", "", response_text).lower()
            if self.secret_clean in cleaned:
                violations.append("Intercepted obfuscated planted secret")

        # Check 3: Canary token match
        if self.canary_token.lower() in response_text.lower():
            violations.append(f"Intercepted operational canary token '{self.canary_token}'")

        # Check 4: Secret prefix pattern
        if not violations:
            pattern = r"NORTHWIND_TEST_KEY_(\d{3,6})"
            if re.search(pattern, response_text, re.IGNORECASE):
                violations.append("Intercepted secret credential pattern")

        if violations:
            return OutputGuardResult(
                is_clean=False,
                filtered_text=self.SAFE_FALLBACK,
                violations=violations,
                action_taken="redacted",
            )

        return OutputGuardResult(
            is_clean=True,
            filtered_text=response_text,
            action_taken="pass",
        )


from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class FindingEvidence(BaseModel):
    """Specific evidence of a security violation."""
    prompt: str = Field(..., description="The attacker/user prompt that caused the failure.")
    response: str = Field(..., description="The LLM/Application response that violated the policy.")
    module_or_probe: str = Field(..., description="The specific probe or module that triggered this (e.g. 'dan.DanInTheWild')")
    additional_context: Optional[Dict[str, Any]] = None

class SentinelFinding(BaseModel):
    """Normalized security finding spanning across all tools."""
    finding_id: str = Field(..., description="Unique ID for the finding group, e.g. SF-2026-001")
    category: str = Field(..., description="Broad category, e.g., 'Jailbreak', 'Prompt Injection', 'Data Leak'")
    source_tool: str = Field(..., description="'garak', 'pyrit', or 'promptfoo'")
    severity: str = Field(..., description="'HIGH', 'MEDIUM', 'LOW'")
    description: str = Field(..., description="Human readable description of the finding.")
    
    owasp_category: Optional[str] = Field(None, description="OWASP Top 10 for LLMs mapping")
    mitre_atlas: Optional[str] = Field(None, description="MITRE ATLAS mapping")
    
    # We group similar evidence together to prevent alert fatigue
    instances: List[FindingEvidence] = Field(default_factory=list, description="All instances of this exact vulnerability type.")
    
    def add_evidence(self, evidence: FindingEvidence):
        self.instances.append(evidence)


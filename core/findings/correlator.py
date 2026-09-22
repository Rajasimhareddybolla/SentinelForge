import json
import glob
from pathlib import Path
from typing import List, Dict, Tuple
import hashlib

from core.findings.models import SentinelFinding, FindingEvidence

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RESULTS_DIR = _PROJECT_ROOT / "results"

def _generate_finding_id(tool: str, category: str) -> str:
    """Generate a stable, unique ID based on the tool and category."""
    hash_input = f"{tool}:{category}".encode('utf-8')
    short_hash = hashlib.sha256(hash_input).hexdigest()[:6].upper()
    return f"SF-2026-{short_hash}"

def _map_frameworks(category: str) -> Tuple[str, str]:
    cat = category.lower()
    if "dan" in cat or "promptinject" in cat:
        return "LLM01: Prompt Injection", "AML.T0051: LLM Prompt Injection"
    elif "encoding" in cat:
        return "LLM01: Prompt Injection (Obfuscation)", "AML.T0043: Craft Adversarial Data"
    elif "pii" in cat or "canary" in cat or "business logic" in cat or "target objective" in cat or "red-teaming" in cat or "crescendo" in cat:
        return "LLM06: Sensitive Information Disclosure", "AML.T0054: LLM Data Leakage"
    return "Unmapped", "Unmapped"

class FindingCorrelator:
    def __init__(self):
        # Maps finding_id -> SentinelFinding
        self.findings: Dict[str, SentinelFinding] = {}
        
    def _get_or_create_finding(self, tool: str, category: str, severity: str, description: str) -> SentinelFinding:
        fid = _generate_finding_id(tool, category)
        if fid not in self.findings:
            owasp, mitre = _map_frameworks(category)
            self.findings[fid] = SentinelFinding(
                finding_id=fid,
                category=category,
                source_tool=tool,
                severity=severity,
                description=description,
                owasp_category=owasp,
                mitre_atlas=mitre
            )
        return self.findings[fid]

    def parse_garak_results(self):
        """Parse all Garak .jsonl traces in results/garak/"""
        garak_dir = _RESULTS_DIR / "garak"
        if not garak_dir.exists(): return
        
        for jsonl_file in garak_dir.glob("*.report.jsonl"):
            with open(jsonl_file, "r") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        record = json.loads(line)
                        if record.get("entry_type") == "attempt":
                            detector_results = record.get("detector_results", {})
                            if not detector_results: continue
                            
                            is_hit = False
                            for det_name, scores in detector_results.items():
                                if any(s > 0 for s in scores):
                                    is_hit = True
                                    break
                                    
                            if is_hit:
                                probe = record.get("probe_classname", "unknown")
                                category = probe.split(".")[0] if "." in probe else probe
                                
                                prompt_data = record.get("prompt", "")
                                if isinstance(prompt_data, str):
                                    prompt = prompt_data
                                else:
                                    prompt = str(prompt_data)
                                    
                                outputs = record.get("outputs", [])
                                response_data = outputs[0] if outputs else ""
                                response = str(response_data) if response_data is not None else ""
                                
                                finding = self._get_or_create_finding(
                                    tool="garak",
                                    category=f"Garak: {category}",
                                    severity="HIGH" if category in ["dan", "promptinject"] else "MEDIUM",
                                    description=f"Garak detected vulnerabilities in the '{category}' probe family."
                                )
                                
                                evidence = FindingEvidence(
                                    prompt=prompt[:1000] + "..." if len(prompt) > 1000 else prompt,
                                    response=response[:1000] + "..." if len(response) > 1000 else response,
                                    module_or_probe=probe
                                )
                                finding.add_evidence(evidence)
                            # Exception logging
                    except Exception as e:
                        import logging
                        logging.error(f"Error parsing Garak record: {e}")

    def parse_promptfoo_results(self):
        """Parse promptfoo_report.json"""
        promptfoo_file = _RESULTS_DIR / "promptfoo_report.json"
        if not promptfoo_file.exists(): return
        
        try:
            with open(promptfoo_file, "r") as f:
                data = json.loads(f.read())
                
            results = data.get("results", [])
            for res in results:
                if not res.get("success", True):
                    # Promptfoo failure
                    prompt = res.get("prompt", {}).get("raw", "")
                    response = res.get("response", {}).get("output", "")
                    test_desc = res.get("test", {}).get("description", "Unknown Test")
                    
                    finding = self._get_or_create_finding(
                        tool="promptfoo",
                        category="Regression Failure",
                        severity="CRITICAL",
                        description="A hardcoded security regression test failed."
                    )
                    
                    evidence = FindingEvidence(
                        prompt=prompt,
                        response=response,
                        module_or_probe=test_desc
                    )
                    finding.add_evidence(evidence)
        except Exception:
            pass

    def parse_pyrit_results(self):
        """Parse pyrit JSON reports"""
        pyrit_dir = _RESULTS_DIR / "pyrit"
        if not pyrit_dir.exists(): return
        
        for pyrit_file in pyrit_dir.glob("pyrit_*.json"):
            try:
                with open(pyrit_file, "r") as f:
                    data = json.loads(f.read())
                    for campaign in data.get("campaigns", []):
                        if campaign.get("compromised", False):
                            category = campaign.get("category", "Target Objective")
                            
                            finding = self._get_or_create_finding(
                                tool="pyrit",
                                category=f"PyRIT: {category}",
                                severity="CRITICAL",
                                description=campaign.get("description", "Autonomous attack succeeded.")
                            )
                            
                            # Find the first turn that leaked
                            earliest = campaign.get("earliest_turn_compromised")
                            turns = campaign.get("turns", [])
                            
                            prompt = "Complex Multi-Turn"
                            response = "Complex Multi-Turn"
                            if earliest and earliest > 0 and earliest <= len(turns):
                                turn = turns[earliest - 1]
                                prompt = turn.get("user_prompt", prompt)
                                response = turn.get("response", response)
                                
                            evidence = FindingEvidence(
                                prompt=prompt,
                                response=response,
                                module_or_probe=campaign.get("name", "Crescendo Attack")
                            )
                            finding.add_evidence(evidence)
            except Exception:
                pass

    def correlate_all(self) -> List[SentinelFinding]:
        self.parse_garak_results()
        self.parse_promptfoo_results()
        self.parse_pyrit_results()
        return list(self.findings.values())

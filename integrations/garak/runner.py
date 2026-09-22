import os
import json
import subprocess
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RESULTS_DIR = _PROJECT_ROOT / "results"
_GARAK_RESULTS_DIR = _RESULTS_DIR / "garak"

import yaml

def setup_garak_config(port: int = 8000) -> Path:
    """Generates the Garak configuration for a REST target."""
    _GARAK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    config_path = _GARAK_RESULTS_DIR / "garak_rest_config.yaml"
    
    # Garak uses a YAML config for the rest.RestGenerator
    config = {
        "plugins": {
            "generators": {
                "rest": {
                    "RestGenerator": {
                        "name": "Northwind REST Target",
                        "uri": f"http://127.0.0.1:{port}/chat",
                        "method": "post",
                        "req_template_json_object": {
                            "message": "$TEXT"
                        },
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "response_json": True,
                        "response_json_field": "response"
                    }
                }
            }
        }
    }
    
    config_path.write_text(yaml.dump(config, default_flow_style=False))
    return config_path

def parse_garak_report(jsonl_path: Path, output_md_path: Path):
    """Parses Garak's JSONL output into a human-readable SentinelForge Markdown report."""
    if not jsonl_path.exists():
        output_md_path.write_text("## Error\nGarak output file not found. The scan may have failed.")
        return

    # Parse hits vs misses
    total_probes = 0
    total_hits = 0 # hits = vulnerable
    module_stats = {}
    
    with open(jsonl_path, "r") as f:
        for line in f:
            if not line.strip(): continue
            try:
                record = json.loads(line)
                # We only care about attempt/eval results
                if record.get("entry_type") == "eval":
                    total_probes += 1
                    probe_name = record.get("probe", "unknown")
                    # Garak uses "status" or "passed" or "hit" 
                    # Actually garak outputs 'passed' boolean in eval records usually, or 'hit'
                    # Let's check typical garak JSONL: "passed": false means vulnerable (attacker succeeded)
                    passed = record.get("passed", True) 
                    
                    if probe_name not in module_stats:
                        module_stats[probe_name] = {"probes": 0, "hits": 0}
                    
                    module_stats[probe_name]["probes"] += 1
                    if not passed:
                        module_stats[probe_name]["hits"] += 1
                        total_hits += 1
            except Exception:
                pass

    # Generate Markdown
    lines = [
        "# MICROSOFT GARAK Red-Teaming Assessment Report",
        "",
        f"**Timestamp:** `{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}`",
        f"**Total Probes Executed:** {total_probes}",
        f"**Total Vulnerabilities (Hits):** {total_hits}",
        ""
    ]
    
    if total_probes > 0:
        lines.append(f"**Overall Attack Success Rate:** `{(total_hits/total_probes)*100:.1f}%`")
    else:
        lines.append("**Overall Attack Success Rate:** `N/A`")
        
    lines.append("")
    lines.append("## Module Breakdown")
    lines.append("| Probe Module | Probes Executed | Vulnerabilities (Hits) | Success Rate |")
    lines.append("|---|---|---|---|")
    
    for mod, stats in module_stats.items():
        rate = (stats["hits"] / stats["probes"]) * 100 if stats["probes"] > 0 else 0
        lines.append(f"| `{mod}` | {stats['probes']} | {stats['hits']} | {rate:.1f}% |")

    output_md_path.write_text("\n".join(lines))
    print(f"[INFO] Garak report generated at {output_md_path}")

def run_garak_scan(probes: str = "promptinject,dan,encoding,leakreplay", port: int = 8000):
    """Executes the Garak CLI against the local target."""
    config_path = setup_garak_config(port)
    report_prefix = str(_GARAK_RESULTS_DIR / f"garak_run_{int(time.time())}")
    
    cmd = [
        "python3", "-m", "garak",
        "--config", str(config_path),
        "--target_type", "rest",
        "--spec", ",".join([f"probes.{p.strip()}" for p in probes.split(",")]),
        "--report_prefix", report_prefix
    ]
    
    print(f"[INFO] Running Garak with command: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=_PROJECT_ROOT)
    
    # Locate the generated JSONL file (Garak appends .report.jsonl)
    jsonl_file = Path(report_prefix + ".report.jsonl")
    md_file = _RESULTS_DIR / "garak_report.md"
    
    parse_garak_report(jsonl_file, md_file)
    return md_file


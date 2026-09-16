"""Integrations package bridging external security scanners (PyRIT, Garak, Promptfoo)
into the unified SentinelForge assessment, scoring, and reporting pipeline.
"""

from integrations.base import BaseScannerAdapter

__all__ = ["BaseScannerAdapter"]


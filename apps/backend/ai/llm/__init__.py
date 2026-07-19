"""Thin Gemini wrapper — the ONLY place in this codebase that calls an LLM.

See client.py's module docstring for the full boundary explanation
(rules.md §4 / CLAUDE.md).
"""

from ai.llm.client import generate_structured

__all__ = ["generate_structured"]

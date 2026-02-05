"""
AI Prompts Module
=================

Centralized prompt templates for AI operations.
"""

from .patient_summary import PATIENT_SUMMARY_PROMPT, PATIENT_SUMMARY_SYSTEM_PROMPT
from .loader import PromptLoader, get_prompt_loader, get_cached_prompt

__all__ = [
    "PATIENT_SUMMARY_PROMPT",
    "PATIENT_SUMMARY_SYSTEM_PROMPT",
    "PromptLoader",
    "get_prompt_loader",
    "get_cached_prompt",
]


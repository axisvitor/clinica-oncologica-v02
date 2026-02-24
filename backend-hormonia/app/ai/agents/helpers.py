from __future__ import annotations

"""Re-export shim for prompt builders and node helpers.

All agent modules import from here instead of directly from app.ai.langgraph.*.
When Phase 12 tombstones app/ai/langgraph/, only this file needs updating.
"""

from app.ai.langgraph.prompts import (  # noqa: F401
    build_empathetic_prompt,
    build_humanization_prompt,
    build_question_variation_prompt,
    build_sentiment_prompt,
)
from app.ai.langgraph.nodes_ai import (  # noqa: F401
    _build_non_repetitive_question,
    _coerce_recent_interactions,
    _extract_recent_questions,
    _is_too_similar_to_recent,
    _replace_patient_name,
)

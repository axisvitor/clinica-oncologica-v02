"""
Unit tests for PersonalizationMixin grounding calibration and helpers.

Proves:
- _personalization_is_grounded() threshold boundaries (R060)
- _select_template_variation() determinism
- _lightly_rephrase_question() question/non-question behaviour
- _personalize_message_ai() AI-skip for expects_response=False

Uses the same module-isolation shim pattern from test_sequential_message_handler.py.
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ── Module-isolation shims ──────────────────────────────────────────
# These must be installed BEFORE any import that touches the handler package.

if "app.services.unified_whatsapp_service" not in sys.modules:
    _whatsapp_module = types.ModuleType("app.services.unified_whatsapp_service")

    class _UnifiedWhatsAppService:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def send_message(self, message, flow_context=None):
            return True

    _whatsapp_module.UnifiedWhatsAppService = _UnifiedWhatsAppService
    sys.modules["app.services.unified_whatsapp_service"] = _whatsapp_module

if "app.services.enhanced_flow_engine" not in sys.modules:
    _engine_module = types.ModuleType("app.services.enhanced_flow_engine")

    class _EnhancedFlowEngine:  # pragma: no cover - test shim
        def __init__(self, db):
            self.db = db

        async def generate_flow_message(self, **kwargs):
            return None

    _engine_module.EnhancedFlowEngine = _EnhancedFlowEngine
    sys.modules["app.services.enhanced_flow_engine"] = _engine_module

# Now safe to import the handler (which pulls in PersonalizationMixin)
from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.models.patient import Patient


# ── Helpers ─────────────────────────────────────────────────────────

def _make_handler(*, use_ai: bool = False) -> SequentialMessageHandler:
    """Build a handler with a mock DB session."""
    db = MagicMock()
    return SequentialMessageHandler(
        db=db,
        use_ai_personalization=use_ai,
    )


def _make_patient(*, patient_id=None, name="Maria") -> Patient:
    """Build a minimal Patient stub."""
    p = MagicMock(spec=Patient)
    p.id = patient_id or uuid4()
    p.name = name
    p.preferred_name = name
    return p


# =====================================================================
# 1. _personalization_is_grounded() — threshold boundary tests
# =====================================================================


class TestPersonalizationIsGrounded:
    """Tests for the grounding gate that prevents hallucinated AI output."""

    def setup_method(self):
        self.h = _make_handler()

    # ── Clear pass: identical text ──

    def test_identical_text_passes(self):
        text = "Como você está se sentindo hoje com o tratamento?"
        assert self.h._personalization_is_grounded(text, text) is True

    # ── Clear fail: completely unrelated ──

    def test_unrelated_text_fails(self):
        base = "Como você está se sentindo hoje com o tratamento?"
        personalized = "A receita de bolo de chocolate leva farinha e ovos."
        assert self.h._personalization_is_grounded(base, personalized) is False

    # ── Anchored reformulation passes ──

    def test_anchored_reformulation_passes(self):
        base = "Como você está se sentindo hoje com o tratamento?"
        personalized = (
            "Maria, como você está se sentindo hoje em relação ao tratamento?"
        )
        assert self.h._personalization_is_grounded(base, personalized) is True

    # ── Hallucinated content fails ──

    def test_hallucinated_content_fails(self):
        base = "Lembre-se de tomar a medicação conforme orientado pelo médico."
        personalized = (
            "Você sabia que a lua influencia o crescimento das plantas? "
            "Aproveite para regar seu jardim nesta fase lunar crescente."
        )
        assert self.h._personalization_is_grounded(base, personalized) is False

    # ── Boundary: high similarity, no keyword overlap ──

    def test_high_similarity_no_keyword_overlap_passes(self):
        # Construct text pairs where similarity >= 0.6 even without 4+ char tokens overlapping
        base = "Olá, tudo bem?"
        # Same structure, slight change — similarity remains high
        personalized = "Olá, tudo bom?"
        sim = self.h._personalization_is_grounded(base, personalized)
        # similarity ratio of these short strings is high (≈0.86), should pass
        assert sim is True

    # ── Boundary: low similarity but good keyword overlap ──

    def test_low_similarity_good_keyword_overlap_passes(self):
        base = (
            "Tratamento quimioterapia sessão medicação orientação oncológica."
        )
        personalized = (
            "A sua sessão de quimioterapia está prevista. "
            "A orientação do tratamento oncológico segue conforme a medicação."
        )
        # Keywords overlap is high (tratamento, quimioterapia, sessão, medicação, orientação, oncológica)
        assert self.h._personalization_is_grounded(base, personalized) is True

    # ── No-keyword path: short content, similarity >= 0.35 ──

    def test_no_keyword_short_content_above_threshold_passes(self):
        # All tokens < 4 chars → no keywords → falls to similarity >= 0.35 path
        base = "Oi, é bom te ver."
        personalized = "Oi, é bom te ver aqui."
        assert self.h._personalization_is_grounded(base, personalized) is True

    def test_no_keyword_short_content_below_threshold_fails(self):
        # All tokens < 4 chars and texts are very different → similarity < 0.35
        base = "Oi, é bom te ver."
        personalized = "Xá, zy qw fj op kl mn."
        assert self.h._personalization_is_grounded(base, personalized) is False

    # ── Empty inputs ──

    def test_empty_base_returns_false(self):
        assert self.h._personalization_is_grounded("", "Algo aqui") is False

    def test_empty_personalized_returns_false(self):
        assert self.h._personalization_is_grounded("Base aqui", "") is False

    def test_both_empty_returns_false(self):
        assert self.h._personalization_is_grounded("", "") is False


# =====================================================================
# 2. _select_template_variation() — determinism tests
# =====================================================================


class TestSelectTemplateVariation:
    """Tests for deterministic variation selection."""

    def setup_method(self):
        self.h = _make_handler()

    def test_determinism_same_inputs(self):
        patient = _make_patient()
        msg = {
            "content": "Base",
            "variations": ["Variação A", "Variação B", "Variação C"],
        }
        result1 = self.h._select_template_variation(
            message=msg, content="Base", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        result2 = self.h._select_template_variation(
            message=msg, content="Base", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        assert result1 == result2

    def test_different_patients_can_get_different_variations(self):
        """With enough variations, different patient IDs should map to different selections."""
        variations = [f"Variação {i}" for i in range(20)]
        msg = {"content": "Base", "variations": variations}

        selections = set()
        for _ in range(10):
            patient = _make_patient(patient_id=uuid4())
            sel = self.h._select_template_variation(
                message=msg, content="Base", patient=patient,
                flow_kind="tratamento", day_number=1, message_index=0,
            )
            selections.add(sel)

        # With 20 variations and 10 random patient IDs, expect at least 2 different selections
        assert len(selections) >= 2

    def test_no_variations_returns_original(self):
        patient = _make_patient()
        msg = {"content": "Base"}
        result = self.h._select_template_variation(
            message=msg, content="Base", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        assert result == "Base"

    def test_empty_variations_list_returns_original(self):
        patient = _make_patient()
        msg = {"content": "Base", "variations": []}
        result = self.h._select_template_variation(
            message=msg, content="Base", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        assert result == "Base"

    def test_duplicate_and_base_identical_variations_filtered(self):
        patient = _make_patient()
        # Variations that are identical to base (after normalize) or duplicates
        msg = {
            "content": "Base Content",
            "variations": ["Base Content", "base content", "  Base  Content  "],
        }
        result = self.h._select_template_variation(
            message=msg, content="Base Content", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        # All variations match base after normalization → returns original
        assert result == "Base Content"

    def test_non_string_variations_skipped(self):
        patient = _make_patient()
        msg = {
            "content": "Base",
            "variations": [None, 123, "", "  ", "Valid variation"],
        }
        result = self.h._select_template_variation(
            message=msg, content="Base", patient=patient,
            flow_kind="tratamento", day_number=1, message_index=0,
        )
        # Only "Valid variation" survives filtering → deterministic pick
        assert result == "Valid variation"


# =====================================================================
# 3. _lightly_rephrase_question() — wrapper tests
# =====================================================================


class TestLightlyRephraseQuestion:
    """Tests for the lightweight question prefix wrapper."""

    def setup_method(self):
        self.h = _make_handler()

    def test_question_gets_prefix(self):
        content = "Como você está se sentindo?"
        result = self.h._lightly_rephrase_question(
            content, day_number=0, message_index=0,
        )
        assert result.endswith("Como você está se sentindo?")
        assert result != content  # prefix was added
        # Must start with one of the known wrappers
        assert any(
            result.startswith(w)
            for w in (
                "Queria te perguntar:",
                "Só para confirmar com você:",
                "Para acompanharmos melhor:",
            )
        )

    def test_non_question_returned_unchanged(self):
        content = "Lembre-se de tomar a medicação conforme orientado."
        result = self.h._lightly_rephrase_question(
            content, day_number=0, message_index=0,
        )
        assert result == content

    def test_existing_prefix_not_double_wrapped(self):
        content = "Queria te perguntar: como vai?"
        result = self.h._lightly_rephrase_question(
            content, day_number=0, message_index=0,
        )
        # Should return content unchanged — prefix already present
        assert result == content

    def test_wrappers_cycle_with_day_and_index(self):
        content = "Tudo certo?"
        wrappers = (
            "Queria te perguntar:",
            "Só para confirmar com você:",
            "Para acompanharmos melhor:",
        )
        seen = set()
        for offset in range(3):
            result = self.h._lightly_rephrase_question(
                content, day_number=offset, message_index=0,
            )
            prefix = result.split(":")[0] + ":"
            seen.add(prefix)

        # All 3 wrappers should be used
        assert len(seen) == 3

    def test_empty_content_returned_unchanged(self):
        result = self.h._lightly_rephrase_question(
            "", day_number=0, message_index=0,
        )
        assert result == ""


# =====================================================================
# 4. _personalize_message_ai() — AI skip for expects_response=False
# =====================================================================


class TestPersonalizeMessageAiSkip:
    """Proves AI engine is never called when expects_response is False."""

    @pytest.mark.asyncio
    async def test_ai_skipped_for_non_response_message(self):
        h = _make_handler(use_ai=True)
        patient = _make_patient(name="João")

        message = {
            "content": "Boa noite, [NOME]. Descanse bem.",
            "expects_response": False,
        }

        with patch(
            "app.services.flow.sequential_message_handler_pkg.personalization.record_ai_fallback"
        ) as mock_fallback:
            result = await h._personalize_message_ai(
                message=message,
                patient=patient,
                day_number=1,
                flow_kind="tratamento",
                day_config=None,
                message_index=0,
            )

        # Fallback content should have [NOME] replaced
        assert "João" in result
        assert "[NOME]" not in result
        # AI fallback recorded with correct reason
        mock_fallback.assert_called_once_with(reason="non_response_message")

    @pytest.mark.asyncio
    async def test_ai_engine_never_instantiated_for_non_response(self):
        """Verify the AI engine is never even accessed."""
        h = _make_handler(use_ai=True)
        patient = _make_patient(name="Ana")

        message = {
            "content": "Bom dia, [NOME].",
            "expects_response": False,
        }

        with patch(
            "app.services.flow.sequential_message_handler_pkg.personalization.record_ai_fallback"
        ):
            await h._personalize_message_ai(
                message=message,
                patient=patient,
                day_number=2,
                flow_kind="tratamento",
                day_config=None,
                message_index=1,
            )

        # _enhanced_flow_engine should remain None — never lazy-initialized
        assert h._enhanced_flow_engine is None

    @pytest.mark.asyncio
    async def test_ai_disabled_records_fallback(self):
        """When use_ai_personalization=False, records ai_disabled reason."""
        h = _make_handler(use_ai=False)
        patient = _make_patient(name="Carlos")

        message = {
            "content": "Olá, [NOME]!",
            "expects_response": True,
        }

        with patch(
            "app.services.flow.sequential_message_handler_pkg.personalization.record_ai_fallback"
        ) as mock_fallback:
            result = await h._personalize_message_ai(
                message=message,
                patient=patient,
                day_number=1,
                flow_kind="tratamento",
                day_config=None,
                message_index=0,
            )

        assert "Carlos" in result
        mock_fallback.assert_called_once_with(reason="ai_disabled")

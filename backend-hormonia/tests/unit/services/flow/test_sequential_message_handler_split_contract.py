from pathlib import Path

from app.services.flow.sequential_message_handler import (
    SequentialMessageHandler as ShimSequentialMessageHandler,
)
from app.services.flow.sequential_message_handler import (
    get_sequential_message_handler as shim_get_sequential_message_handler,
)
from app.services.flow.sequential_message_handler_pkg.service import (
    SequentialMessageHandler as CanonicalSequentialMessageHandler,
)
from app.services.flow.sequential_message_handler_pkg.service import (
    get_sequential_message_handler as canonical_get_sequential_message_handler,
)


def test_shim_resolves_to_canonical() -> None:
    assert ShimSequentialMessageHandler is CanonicalSequentialMessageHandler


def test_factory_function_reexported() -> None:
    assert callable(shim_get_sequential_message_handler)
    assert shim_get_sequential_message_handler is canonical_get_sequential_message_handler


def test_split_files_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[4]
    files = [
        root / "app/services/flow/sequential_message_handler_pkg/sequencing.py",
        root / "app/services/flow/sequential_message_handler_pkg/state.py",
        root / "app/services/flow/sequential_message_handler_pkg/personalization.py",
        root / "app/services/flow/sequential_message_handler_pkg/quiz.py",
        root / "app/services/flow/sequential_message_handler_pkg/service.py",
    ]

    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"


def test_responsibilities_split_by_module() -> None:
    assert (
        CanonicalSequentialMessageHandler.send_day_messages.__module__
        == "app.services.flow.sequential_message_handler_pkg.sequencing"
    )
    assert (
        CanonicalSequentialMessageHandler._get_or_create_flow_state.__module__
        == "app.services.flow.sequential_message_handler_pkg.state"
    )
    assert (
        CanonicalSequentialMessageHandler._personalize_message_ai.__module__
        == "app.services.flow.sequential_message_handler_pkg.personalization"
    )
    assert (
        CanonicalSequentialMessageHandler._inject_quiz_link_if_needed.__module__
        == "app.services.flow.sequential_message_handler_pkg.quiz"
    )

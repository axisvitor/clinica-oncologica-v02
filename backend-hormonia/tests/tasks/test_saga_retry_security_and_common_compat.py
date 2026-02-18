"""Focused tests for saga retry HTML escaping."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

def _load_module(module_name: str, relative_path: str):
    file_path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_send_admin_email_alert_escapes_dynamic_html_values():
    module = _load_module("saga_retry_under_test", "app/tasks/saga_retry.py")
    captured: dict = {}

    fake_email_module = types.ModuleType("app.services.email")

    async def _fake_send_email(**kwargs):
        captured.update(kwargs)

    fake_email_module.send_email = _fake_send_email

    saga = SimpleNamespace(
        id='abc"><script>alert(1)</script>',
        patient_id='<img src=x onerror="alert(2)">',
        doctor_id='<b onclick="alert(3)">doc</b>',
        status='FAILED<script>alert(4)</script>',
        retry_count=5,
        current_step='step"><img src=x onerror=alert(5)>',
        created_at="2026-01-01 00:00:00+00:00",
        last_retry_at="2026-01-01 01:00:00+00:00",
        error_message='<script>alert("boom")</script>',
    )

    with patch.dict(sys.modules, {"app.services.email": fake_email_module}), patch.object(
        module.settings,
        "APP_ADMIN_DASHBOARD_URL",
        'https://admin.example.com/" onmouseover="alert(9)"',
        create=True,
    ):
        asyncio.run(module._send_admin_email_alert(saga))

    html_content = captured["html_content"]

    assert 'abc"><script>alert(1)</script>' not in html_content
    assert "abc&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html_content
    assert '<img src=x onerror="alert(2)">' not in html_content
    assert "&lt;img src=x onerror=&quot;alert(2)&quot;&gt;" in html_content
    assert '<script>alert("boom")</script>' not in html_content
    assert "&lt;script&gt;alert(&quot;boom&quot;)&lt;/script&gt;" in html_content
    assert '" onmouseover="alert(9)"' not in html_content
    assert "%22%3E%3Cscript%3Ealert%281%29%3C%2Fscript%3E" in html_content
    assert captured["to_email"]

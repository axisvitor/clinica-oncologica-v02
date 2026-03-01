import pytest

from app.integrations.evolution import EvolutionClient


@pytest.mark.asyncio
async def test_send_text_message_includes_text_field(monkeypatch):
    """Ensure send_text_message uses the format required by Evolution API."""
    client = EvolutionClient(
        base_url="https://api.evolution.dev",
        instance_name="instancia-teste",
        api_key="fake-key",
    )

    captured = {}

    async def fake_make_request(method, endpoint, data, params=None, retry_count=0):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {"status": "success", "data": {"id": "123"}}

    monkeypatch.setattr(client.request_handler, "make_request", fake_make_request)

    try:
        response = await client.send_text_message("94991307744", "Hello patient", delay=750)
    finally:
        await client.close()

    assert response["data"]["id"] == "123"
    assert captured["method"] == "POST"
    assert captured["endpoint"] == "message/sendText/instancia-teste"
    assert captured["data"]["number"] == "5594991307744"  # 55 prefix is added automatically
    assert captured["data"]["text"] == "Hello patient"
    assert captured["data"]["delay"] == 750
    assert "textMessage" not in captured["data"]

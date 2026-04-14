import app.code as code_module

from conftest import make_app


def test_code_generate_requires_task():
    client = make_app().test_client()
    resp = client.post("/api/code/generate", json={"task": "", "language": "python", "framework": "Flask"})
    assert resp.status_code == 400


def test_code_generate_returns_ai_payload(monkeypatch):
    app = make_app()
    client = app.test_client()

    def fake_generate_code_content(prompt: str, framework: str, language: str, conversation_id: str = "", fresh_conversation: bool = False):
        return {
            "prompt": prompt,
            "framework": framework,
            "language": language,
            "content": "print('hello world')",
            "source": "ai-model",
            "conversation_id": conversation_id or "conv-1",
            "is_fresh_conversation": fresh_conversation,
            "conversation_expired": False,
            "conversation_timeout_seconds": 300,
        }

    monkeypatch.setattr("app.routes.generate_code_content", fake_generate_code_content)

    resp = client.post(
        "/api/code/generate",
        json={"task": "make hello world", "language": "python", "framework": "Flask"},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["language"] == "python"
    assert payload["framework"] == "Flask"
    assert payload["source"] == "ai-model"
    assert payload["content"] == "print('hello world')"
    assert payload["conversation_id"] == "conv-1"


def test_code_generate_returns_503_when_unconfigured(monkeypatch):
    app = make_app()
    client = app.test_client()

    monkeypatch.setattr("app.routes.generate_code_content", lambda **kwargs: None)

    resp = client.post(
        "/api/code/generate",
        json={"task": "make hello world", "language": "python", "framework": "Flask"},
    )

    assert resp.status_code == 503


def test_code_generate_returns_502_on_runtime_error(monkeypatch):
    app = make_app()
    client = app.test_client()

    def fake_generate_code_content(**kwargs):
        raise RuntimeError("AI model request failed: boom")

    monkeypatch.setattr("app.routes.generate_code_content", fake_generate_code_content)

    resp = client.post(
        "/api/code/generate",
        json={"task": "make hello world", "language": "python", "framework": "Flask"},
    )

    assert resp.status_code == 502


def test_code_generate_passes_conversation_context(monkeypatch):
    app = make_app()
    client = app.test_client()
    captured = {}

    def fake_generate_code_content(prompt: str, framework: str, language: str, conversation_id: str = "", fresh_conversation: bool = False):
        captured["conversation_id"] = conversation_id
        captured["fresh_conversation"] = fresh_conversation
        return {
            "prompt": prompt,
            "framework": framework,
            "language": language,
            "content": "ok",
            "source": "ai-model",
            "conversation_id": conversation_id or "conv-2",
            "is_fresh_conversation": fresh_conversation,
            "conversation_expired": False,
            "conversation_timeout_seconds": 300,
        }

    monkeypatch.setattr("app.routes.generate_code_content", fake_generate_code_content)

    resp = client.post(
        "/api/code/generate",
        json={
            "task": "continue this code",
            "language": "python",
            "framework": "Flask",
            "conversation_id": "existing-conv",
            "fresh_conversation": False,
        },
    )

    assert resp.status_code == 200
    assert captured["conversation_id"] == "existing-conv"
    assert captured["fresh_conversation"] is False


def test_code_conversation_expires_after_timeout():
    code_module.CODE_CONVERSATIONS.clear()

    conversation_id, messages, is_fresh, expired = code_module._resolve_conversation(
        conversation_id="",
        fresh_conversation=False,
        now=1000.0,
    )
    assert is_fresh is True
    assert expired is False
    assert messages == []

    code_module._store_conversation_messages(
        conversation_id,
        [{"role": "user", "content": "hello"}],
        now=1001.0,
    )

    same_id, same_messages, same_is_fresh, same_expired = code_module._resolve_conversation(
        conversation_id=conversation_id,
        fresh_conversation=False,
        now=1200.0,
    )
    assert same_id == conversation_id
    assert same_is_fresh is False
    assert same_expired is False
    assert same_messages == [{"role": "user", "content": "hello"}]

    new_id, new_messages, new_is_fresh, new_expired = code_module._resolve_conversation(
        conversation_id=conversation_id,
        fresh_conversation=False,
        now=1405.0,
    )
    assert new_id != conversation_id
    assert new_messages == []
    assert new_is_fresh is True
    assert new_expired is True

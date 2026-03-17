from io import BytesIO

from PIL import Image

import app.code as code_module
from app import create_app


def test_index_page():
    app = create_app()
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'id="app"' in resp.data


def test_seo_page():
    app = create_app()
    client = app.test_client()
    resp = client.get("/seo")
    assert resp.status_code == 200
    assert b'id="seo-app"' in resp.data


def test_code_page():
    app = create_app()
    client = app.test_client()
    resp = client.get("/code")
    assert resp.status_code == 200
    assert b'id="code-app"' in resp.data


def _make_logo_bytes() -> BytesIO:
    img = Image.new("RGB", (40, 40), "red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_qr_png():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        json={
            "data": "hello",
            "format": "png",
            "qr_color": "#1144aa",
            "border_color": "#ff6600",
        },
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:4] == b"\x89PNG"


def test_qr_svg():
    app = create_app()
    client = app.test_client()
    resp = client.post("/api/qr", json={"data": "hello", "format": "svg"})
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
    assert b"<svg" in resp.data[:200]


def test_qr_preview_returns_png_inline():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr/preview",
        data={"data": "hello", "qr_color": "#112233", "border_color": "#000000"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data[:4] == b"\x89PNG"


def test_qr_png_with_logo_upload():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "png",
            "logo": (_make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_svg_with_logo_returns_400():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/qr",
        data={
            "data": "hello",
            "format": "svg",
            "logo": (_make_logo_bytes(), "logo.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_seo_generate_success():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "youtube",
            "topic": "How to grow a faceless YouTube channel",
            "live": False,
            "content_format": "long",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["platform"] == "youtube"
    assert len(payload["titles"]) >= 3
    assert payload["description"]
    assert len(payload["hashtags"]) >= 5
    assert len(payload["seo_tags"]) >= 5
    assert len(payload["thumbnail_ideas"]) >= 2
    assert len(payload["thumbnail_text"]) >= 2
    assert payload["content_format"] == "long"
    assert payload["quality_scores"]["overall_score"] >= 0
    assert "title_readability" in payload["quality_scores"]
    assert "description_readability" in payload["quality_scores"]
    assert "validation" in payload
    assert "candidate_sources" in payload


def test_seo_generate_exposes_score_breakdown_types():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "youtube",
            "topic": "How to build a strong personal brand on LinkedIn",
            "live": False,
            "content_format": "long",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()

    quality_scores = payload["quality_scores"]
    assert isinstance(quality_scores["best_title_score"], int)
    assert isinstance(quality_scores["description_score"], int)
    assert isinstance(quality_scores["hashtags_score"], int)
    assert isinstance(quality_scores["seo_tags_score"], int)
    assert isinstance(quality_scores["thumbnail_text_score"], int)
    assert isinstance(quality_scores["overall_score"], int)

    title_readability = quality_scores["title_readability"]
    assert "flesch_reading_ease" in title_readability
    assert "flesch_kincaid_grade" in title_readability
    assert "readability_score" in title_readability

    description_readability = quality_scores["description_readability"]
    assert "flesch_reading_ease" in description_readability
    assert "flesch_kincaid_grade" in description_readability
    assert "readability_score" in description_readability


def test_seo_generate_instagram_success():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "instagram",
            "topic": "How to write better hooks for reels",
            "live": False,
            "content_format": "reel",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["platform"] == "instagram"
    assert payload["content_format"] == "reel"
    assert payload["description"]
    assert payload["hook"]
    assert payload["cta"]
    assert isinstance(payload["caption_variants"], list)
    assert isinstance(payload["visual_direction"], list)


def test_seo_generate_linkedin_success():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "linkedin",
            "topic": "How founders should write better LinkedIn posts",
            "live": False,
            "content_format": "post",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["platform"] == "linkedin"
    assert payload["content_format"] == "post"
    assert payload["description"]
    assert payload["hook"]
    assert payload["cta"]
    assert isinstance(payload["post_variants"], list)


def test_seo_generate_validation_check_structure():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "youtube",
            "topic": "Best morning workout for fat loss",
            "live": False,
            "content_format": "short",
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()

    validation = payload["validation"]
    assert isinstance(validation["passed"], bool)
    assert isinstance(validation["checks"]["best_title"], bool)
    assert isinstance(validation["checks"]["description"], bool)
    assert isinstance(validation["checks"]["title_readability"], bool)
    assert isinstance(validation["checks"]["description_readability"], bool)
    assert isinstance(validation["checks"]["hashtags"], bool)
    assert isinstance(validation["checks"]["seo_tags"], bool)
    assert isinstance(validation["checks"]["thumbnail_text"], bool)


def test_seo_generate_requires_topic():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={"platform": "youtube", "topic": "", "live": False, "content_format": "short"},
    )
    assert resp.status_code == 400


def test_seo_generate_falls_back_when_personal_key_missing():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "youtube",
            "topic": "how to edit reels fast",
            "live": True,
            "use_own_key": True,
            "youtube_api_key": "",
            "allow_fallback": True,
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["source"] == "local-rules"
    assert "live_error" in payload


def test_seo_generate_requires_personal_key_without_fallback():
    app = create_app()
    client = app.test_client()
    resp = client.post(
        "/api/seo/generate",
        json={
            "platform": "youtube",
            "topic": "how to edit reels fast",
            "live": True,
            "use_own_key": True,
            "youtube_api_key": "",
            "allow_fallback": False,
        },
    )
    assert resp.status_code == 400


def test_qr_api_requires_data():
    app = create_app()
    client = app.test_client()
    resp = client.post("/api/qr", json={"data": "", "format": "png"})
    assert resp.status_code == 400


def test_code_generate_requires_task():
    app = create_app()
    client = app.test_client()
    resp = client.post("/api/code/generate", json={"task": "", "language": "python", "framework": "Flask"})
    assert resp.status_code == 400


def test_code_generate_returns_ai_payload(monkeypatch):
    app = create_app()
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
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr("app.routes.generate_code_content", lambda **kwargs: None)

    resp = client.post(
        "/api/code/generate",
        json={"task": "make hello world", "language": "python", "framework": "Flask"},
    )

    assert resp.status_code == 503


def test_code_generate_returns_502_on_runtime_error(monkeypatch):
    app = create_app()
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
    app = create_app()
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

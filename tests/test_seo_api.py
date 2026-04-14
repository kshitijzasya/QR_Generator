from conftest import make_client


def test_seo_generate_success():
    client = make_client()
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
    client = make_client()
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
    client = make_client()
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
    client = make_client()
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
    client = make_client()
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
    client = make_client()
    resp = client.post(
        "/api/seo/generate",
        json={"platform": "youtube", "topic": "", "live": False, "content_format": "short"},
    )
    assert resp.status_code == 400


def test_seo_generate_falls_back_when_personal_key_missing():
    client = make_client()
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
    client = make_client()
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

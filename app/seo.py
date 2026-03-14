from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log10
import json
import os
from pathlib import Path
import re
from typing import Any

try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

try:
    import yake
except ImportError:
    yake = None

try:
    import textstat
except ImportError:
    textstat = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}

TITLE_PATTERNS = [
    "{primary}: What Actually Matters",
    "{primary} Explained for {audience}",
    "{primary}: Biggest Mistakes to Avoid",
    "{primary} Strategy That Works in {year}",
    "{primary} vs {secondary}: Which Wins?",
    "What Changed in {primary} ({year})",
]

PLATFORM_OUTPUT_MAP: dict[str, dict[str, Any]] = {
    "youtube": {
        "required_sections": ["titles", "description", "seo_tags", "hashtags", "thumbnail_text", "thumbnail_ideas"],
        "title_count": 6,
        "description_count": 1,
        "tag_label": "seo_tags",
    },
    "instagram": {
        "required_sections": ["titles", "description", "hashtags"],
        "title_count": 4,
        "description_count": 1,
        "tag_label": "hashtags",
    },
}


@dataclass
class SocialRules:
    platform: str
    max_titles: int
    max_hashtags: int
    title_templates: list[str]
    description_templates: list[str]
    thumbnail_idea_templates: list[str]
    thumbnail_text_templates: list[str]
    hashtags_base: list[str]
    seo_tag_templates: list[str]


@dataclass
class CompetitorVideo:
    video_id: str
    title: str
    description: str
    channel: str
    tags: list[str]
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    duration_seconds: int
    rank_score: float = 0.0


def _rules_path(platform: str) -> Path:
    return Path(__file__).resolve().parent.parent / "rules" / "socialmedia" / f"{platform}.json"


def _output_rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / "rules" / "socialmedia" / "output_rules.json"


def _load_rules(platform: str) -> SocialRules:
    rules_file = _rules_path(platform)
    if not rules_file.exists():
        raise ValueError("Unsupported platform")

    with rules_file.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return SocialRules(
        platform=payload.get("platform", platform),
        max_titles=int(payload.get("max_titles", 6)),
        max_hashtags=int(payload.get("max_hashtags", 12)),
        title_templates=payload.get("title_templates", []),
        description_templates=payload.get("description_templates", []),
        thumbnail_idea_templates=payload.get("thumbnail_idea_templates", []),
        thumbnail_text_templates=payload.get("thumbnail_text_templates", []),
        hashtags_base=payload.get("hashtags_base", []),
        seo_tag_templates=payload.get("seo_tag_templates", []),
    )


def _load_output_rules() -> dict[str, Any]:
    rules_file = _output_rules_path()
    if not rules_file.exists():
        return {}
    with rules_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def _topic_keywords(topic: str) -> list[str]:
    parts = re.findall(r"[a-zA-Z0-9]+", topic.lower())
    keywords: list[str] = []

    for word in parts:
        if word in STOP_WORDS:
            continue
        if word not in keywords:
            keywords.append(word)

    return keywords


def _extract_keywords_fallback(texts: list[str], limit: int = 16) -> list[str]:
    frequencies: dict[str, int] = {}
    for text in texts:
        for word in re.findall(r"[a-zA-Z0-9]+", (text or "").lower()):
            if len(word) < 3 or word in STOP_WORDS:
                continue
            frequencies[word] = frequencies.get(word, 0) + 1

    sorted_words = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in sorted_words[:limit]]


def _extract_phrases(texts: list[str], limit: int = 18) -> list[str]:
    joined = "\n".join(texts).strip()
    if not joined:
        return []

    if yake is not None:
        extractor = yake.KeywordExtractor(lan="en", n=3, top=limit * 2, dedupLim=0.85)
        phrases = [item for item, _score in extractor.extract_keywords(joined)]
        return _dedupe_case_insensitive(phrases, limit=limit)

    return _extract_keywords_fallback(texts, limit=limit)


def _to_hashtag(text: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", text)
    compact = "".join(word.capitalize() for word in words)
    return f"#{compact}" if compact else ""


def _format_values(topic: str, keyword1: str, keyword2: str) -> dict[str, str]:
    return {
        "topic": topic,
        "keyword1": keyword1,
        "keyword2": keyword2,
        "year": str(datetime.utcnow().year),
    }


def _render_templates(templates: list[str], values: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for template in templates:
        item = template.format(**values).strip()
        if item and item not in rendered:
            rendered.append(item)
    return rendered


def _dedupe_case_insensitive(items: list[str], limit: int | None = None) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for item in items:
        candidate = (item or "").strip()
        if not candidate:
            continue

        lowered = candidate.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        output.append(candidate)

        if limit and len(output) >= limit:
            break

    return output


def _normalize_content_format(content_format: str) -> str:
    normalized = (content_format or "long").strip().lower()
    return "short" if normalized == "short" else "long"


def _youtube_api_key() -> str:
    return (os.getenv("YOUTUBE_API_KEY") or "").strip()


def _nvidia_api_key() -> str:
    return (os.getenv("NVIDIA_API_KEY") or "").strip()


def _nvidia_model_name() -> str:
    return (os.getenv("NVIDIA_MODEL_NAME") or "nvidia/nvidia-nemotron-nano-9b-v2").strip()


def _build_youtube_service(api_key: str = "", use_env_fallback: bool = True):
    resolved_key = (api_key or "").strip()
    if not resolved_key and use_env_fallback:
        resolved_key = _youtube_api_key()
    if not resolved_key:
        raise RuntimeError("YouTube API key is missing")
    if build is None:
        raise RuntimeError("google-api-python-client is not installed")
    return build("youtube", "v3", developerKey=resolved_key, cache_discovery=False)


def _query_variants(topic: str, content_format: str) -> list[str]:
    base = [topic, f"{topic} explained", f"{topic} tips"]
    if content_format == "short":
        base.insert(1, f"{topic} shorts")
    return _dedupe_case_insensitive(base, limit=3)


def _duration_values(content_format: str) -> list[str | None]:
    if content_format == "short":
        return ["short"]
    return ["medium", "long"]


def _youtube_search_ids(
    service,
    topic: str,
    content_format: str,
    max_results: int = 10,
) -> list[str]:
    video_ids: list[str] = []
    seen_ids: set[str] = set()

    for query in _query_variants(topic, content_format):
        for duration in _duration_values(content_format):
            request = service.search().list(
                part="snippet",
                q=query,
                type="video",
                order="relevance",
                maxResults=max_results,
                regionCode="US",
                relevanceLanguage="en",
                safeSearch="none",
                videoDuration=duration,
            )
            response = request.execute()
            for item in response.get("items", []):
                video_id = item.get("id", {}).get("videoId", "").strip()
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)
                    video_ids.append(video_id)
            if len(video_ids) >= 18:
                return video_ids[:18]

    return video_ids[:18]


def _parse_duration_seconds(duration_text: str) -> int:
    match = re.fullmatch(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        duration_text or "",
    )
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def _fetch_youtube_competitors(
    topic: str,
    content_format: str,
    api_key: str = "",
    use_env_fallback: bool = True,
) -> list[CompetitorVideo]:
    try:
        service = _build_youtube_service(api_key=api_key, use_env_fallback=use_env_fallback)
        video_ids = _youtube_search_ids(service, topic=topic, content_format=content_format)
        if not video_ids:
            return []

        response = service.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
            maxResults=len(video_ids),
        ).execute()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"YouTube live fetch failed: {exc}") from exc

    competitors: list[CompetitorVideo] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})
        competitors.append(
            CompetitorVideo(
                video_id=item.get("id", ""),
                title=(snippet.get("title") or "").strip(),
                description=(snippet.get("description") or "").strip(),
                channel=(snippet.get("channelTitle") or "").strip(),
                tags=[tag.strip() for tag in snippet.get("tags", []) if str(tag).strip()],
                published_at=(snippet.get("publishedAt") or "").strip(),
                view_count=int(statistics.get("viewCount", 0) or 0),
                like_count=int(statistics.get("likeCount", 0) or 0),
                comment_count=int(statistics.get("commentCount", 0) or 0),
                duration_seconds=_parse_duration_seconds(content_details.get("duration", "")),
            )
        )

    return [item for item in competitors if item.title]


def _safe_ratio(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(max(value / max_value, 0.0), 1.0)


def _keyword_match_score(video: CompetitorVideo, topic_keywords: list[str]) -> float:
    haystack = " ".join([video.title, video.description] + video.tags).lower()
    if not topic_keywords:
        return 0.0
    hits = sum(1 for keyword in topic_keywords if keyword in haystack)
    return _safe_ratio(hits, len(topic_keywords))


def _title_quality_score(title: str, topic_keywords: list[str], output_rules: dict[str, Any]) -> float:
    title_rules = output_rules.get("title_rules", {})
    min_chars = int(title_rules.get("min_chars", 35))
    max_chars = int(title_rules.get("max_chars", 60))
    length = len(title.strip())

    if length < min_chars:
        length_score = _safe_ratio(length, min_chars)
    elif length > max_chars:
        length_score = max(0.0, 1 - ((length - max_chars) / max_chars))
    else:
        length_score = 1.0

    lowered = title.lower()
    keyword_score = 0.0
    if topic_keywords:
        keyword_score = _safe_ratio(sum(1 for keyword in topic_keywords if keyword in lowered), min(3, len(topic_keywords)))
        front_keyword = sum(1 for keyword in topic_keywords[:2] if keyword in lowered[: max(1, len(lowered) // 2)])
        keyword_score = min(1.0, (keyword_score * 0.7) + (_safe_ratio(front_keyword, 2) * 0.3))

    curiosity_bonus = 0.15 if any(token in title for token in ["?", "vs", "Explained", "Why", "What"]) else 0.0
    return min(1.0, (length_score * 0.45) + (keyword_score * 0.4) + curiosity_bonus)


def _freshness_score(published_at: str) -> float:
    if not published_at:
        return 0.0
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0

    days_old = max((datetime.now(timezone.utc) - published).days, 0)
    if days_old <= 30:
        return 1.0
    if days_old <= 180:
        return 0.75
    if days_old <= 365:
        return 0.5
    return 0.25


def _views_signal_score(view_count: int, max_view_count: int) -> float:
    if view_count <= 0 or max_view_count <= 0:
        return 0.0
    return _safe_ratio(log10(view_count + 1), log10(max_view_count + 1))


def _engagement_signal_score(video: CompetitorVideo) -> float:
    if video.view_count <= 0:
        return 0.0
    engagement = (video.like_count + (video.comment_count * 2)) / max(video.view_count, 1)
    return min(1.0, engagement * 50)


def _rank_competitors(
    competitors: list[CompetitorVideo],
    topic_keywords: list[str],
    output_rules: dict[str, Any],
) -> list[CompetitorVideo]:
    if not competitors:
        return []

    weights = (
        output_rules.get("competitor_scoring_rules", {}).get("weights", {})
        if output_rules
        else {}
    )
    max_view_count = max((video.view_count for video in competitors), default=0)

    for video in competitors:
        keyword_match = _keyword_match_score(video, topic_keywords)
        title_quality = _title_quality_score(video.title, topic_keywords, output_rules)
        freshness = _freshness_score(video.published_at)
        views_signal = _views_signal_score(video.view_count, max_view_count)
        engagement_signal = _engagement_signal_score(video)

        video.rank_score = (
            keyword_match * float(weights.get("keyword_match", 0.3))
            + title_quality * float(weights.get("title_quality", 0.2))
            + freshness * float(weights.get("freshness", 0.15))
            + views_signal * float(weights.get("views_signal", 0.2))
            + engagement_signal * float(weights.get("engagement_signal", 0.15))
        )

    return sorted(competitors, key=lambda item: item.rank_score, reverse=True)


def _build_local_response(topic: str, rules: SocialRules, content_format: str, output_rules: dict[str, Any]) -> dict:
    keywords = _topic_keywords(topic)
    keyword1 = keywords[0] if keywords else "growth"
    keyword2 = keywords[1] if len(keywords) > 1 else "strategy"

    values = _format_values(topic, keyword1, keyword2)

    titles = _render_templates(rules.title_templates, values)[: rules.max_titles]
    description_lines = _render_templates(rules.description_templates, values)
    descriptions = [" ".join(description_lines)] if description_lines else []

    dynamic_hashtags = [_to_hashtag(topic)] + [_to_hashtag(k) for k in keywords[:8]]
    hashtags = []
    for tag in rules.hashtags_base + dynamic_hashtags:
        if not tag:
            continue
        norm = tag if tag.startswith("#") else f"#{tag}"
        if norm.lower() not in {item.lower() for item in hashtags}:
            hashtags.append(norm)
        if len(hashtags) >= rules.max_hashtags:
            break

    seo_tags = _render_templates(rules.seo_tag_templates, values)
    seo_tags.extend([keyword1, keyword2, f"{topic} content", f"{content_format} video"])
    unique_seo_tags = _dedupe_case_insensitive(seo_tags, limit=20)

    thumbnail_ideas = _render_templates(rules.thumbnail_idea_templates, values)
    thumbnail_text = _render_templates(rules.thumbnail_text_templates, values)

    response = {
        "platform": rules.platform,
        "topic": topic,
        "content_format": content_format,
        "titles": titles,
        "description": descriptions[0] if descriptions else "",
        "hashtags": hashtags,
        "seo_tags": unique_seo_tags,
        "thumbnail_ideas": thumbnail_ideas,
        "thumbnail_text": thumbnail_text,
        "source": "local-rules",
        "candidate_sources": ["local-rules"],
        "research": {
            "competitors": [],
            "keyword_buckets": {"primary": keywords[:5], "supporting": keywords[5:10], "broad": []},
        },
    }
    return _attach_quality_scores(response, output_rules)


def _bucket_keywords(phrases: list[str], topic_keywords: list[str], output_rules: dict[str, Any]) -> dict[str, list[str]]:
    bucket_rules = output_rules.get("keyword_bucket_rules", {}).get("buckets", {})
    primary_max = int(bucket_rules.get("primary", {}).get("max_items", 7))
    supporting_max = int(bucket_rules.get("supporting", {}).get("max_items", 7))
    broad_max = int(bucket_rules.get("broad", {}).get("max_items", 7))

    primary: list[str] = []
    supporting: list[str] = []
    broad: list[str] = []

    topic_keyword_set = set(topic_keywords)
    for phrase in phrases:
        words = set(_topic_keywords(phrase))
        if words & topic_keyword_set and len(primary) < primary_max:
            primary.append(phrase)
        elif len(words) >= 2 and len(supporting) < supporting_max:
            supporting.append(phrase)
        elif len(broad) < broad_max:
            broad.append(phrase)

    return {
        "primary": primary,
        "supporting": supporting,
        "broad": broad,
    }


def _generate_titles(
    topic: str,
    content_format: str,
    phrases: list[str],
    competitors: list[CompetitorVideo],
    rules: SocialRules,
    output_rules: dict[str, Any],
) -> list[str]:
    audience = "Shorts" if content_format == "short" else "Creators"
    primary = phrases[0] if phrases else topic
    secondary = phrases[1] if len(phrases) > 1 else "results"
    year = str(datetime.utcnow().year)

    generated = [
        pattern.format(primary=primary, secondary=secondary, audience=audience, year=year)
        for pattern in TITLE_PATTERNS
    ]
    generated.extend(video.title for video in competitors[:3])
    generated.extend(
        _render_templates(
            rules.title_templates,
            _format_values(topic, primary, secondary),
        )
    )

    generated = _dedupe_case_insensitive(generated)
    scored = sorted(
        generated,
        key=lambda title: _title_quality_score(title, _topic_keywords(topic), output_rules),
        reverse=True,
    )
    return scored[: rules.max_titles]


def _generate_description(topic: str, phrases: list[str], competitors: list[CompetitorVideo]) -> str:
    primary = phrases[0] if phrases else topic
    secondary = phrases[1] if len(phrases) > 1 else topic
    channels = _dedupe_case_insensitive([video.channel for video in competitors], limit=2)
    if channels:
        channel_line = f"After reviewing what works for {', '.join(channels)},"
    else:
        channel_line = "After reviewing top-performing videos,"

    return (
        f"{primary} is driving attention right now. {channel_line} this angle focuses on {secondary} "
        f"and gives viewers a clear reason to click. Watch through for the key context, the practical takeaway, "
        f"and the next step you should apply today."
    )


def _generate_hashtags(topic: str, phrases: list[str], rules: SocialRules) -> list[str]:
    tags = list(rules.hashtags_base)
    tags.extend(_to_hashtag(topic) for _ in [0])
    tags.extend(_to_hashtag(phrase) for phrase in phrases[:10])
    output: list[str] = []
    for tag in tags:
        if not tag:
            continue
        normalized = tag if tag.startswith("#") else f"#{tag}"
        if normalized.lower() in {item.lower() for item in output}:
            continue
        output.append(normalized)
        if len(output) >= rules.max_hashtags:
            break
    return output


def _generate_seo_tags(topic: str, phrases: list[str], competitors: list[CompetitorVideo], output_rules: dict[str, Any]) -> list[str]:
    tag_rules = output_rules.get("seo_tag_rules", {})
    max_count = int(tag_rules.get("max_count", 20))
    candidates = [topic, f"{topic} youtube", f"{topic} tips", f"{topic} explained"]
    candidates.extend(phrases)
    candidates.extend(tag for video in competitors[:3] for tag in video.tags[:6])
    return _dedupe_case_insensitive(candidates, limit=max_count)


def _generate_thumbnail_text(phrases: list[str], rules: SocialRules) -> list[str]:
    generated = []
    for phrase in phrases[:4]:
        words = phrase.split()
        if 1 <= len(words) <= 4:
            generated.append(phrase.upper())
    generated.extend(rules.thumbnail_text_templates)
    return _dedupe_case_insensitive(generated, limit=6)


def _generate_thumbnail_ideas(topic: str, competitors: list[CompetitorVideo], rules: SocialRules) -> list[str]:
    ideas = [
        f"Main object close-up with conflict overlay for {topic}",
        f"Before vs after frame centered on {topic}",
    ]
    ideas.extend(f"Visual angle from competitor title: {video.title[:75]}" for video in competitors[:2])
    ideas.extend(rules.thumbnail_idea_templates)
    return _dedupe_case_insensitive(ideas, limit=6)


def _platform_requirements(platform: str) -> dict[str, Any]:
    return PLATFORM_OUTPUT_MAP.get(platform, PLATFORM_OUTPUT_MAP["youtube"])


def _build_ai_prompt(
    topic: str,
    platform: str,
    content_format: str,
    competitors: list[CompetitorVideo],
    keyword_buckets: dict[str, list[str]],
) -> tuple[str, str]:
    requirements = _platform_requirements(platform)
    competitor_lines = []
    for item in competitors[:5]:
        competitor_lines.append(
            f"- {item.title} | channel={item.channel} | views={item.view_count} | tags={', '.join(item.tags[:6])}"
        )

    system_prompt = (
        "You are an SEO strategist. Return only valid JSON with no markdown. "
        "Use the research context and platform requirements. Do not fabricate unrelated trends."
    )
    user_prompt = (
        f"Platform: {platform}\n"
        f"Content format: {content_format}\n"
        f"Topic: {topic}\n"
        f"Required sections: {', '.join(requirements['required_sections'])}\n"
        f"Keyword buckets: {json.dumps(keyword_buckets)}\n"
        f"Top competitors:\n" + "\n".join(competitor_lines) + "\n\n"
        "Return JSON with keys:\n"
        "{\n"
        '  "titles": [string],\n'
        '  "description": string,\n'
        '  "hashtags": [string],\n'
        '  "seo_tags": [string],\n'
        '  "thumbnail_text": [string],\n'
        '  "thumbnail_ideas": [string]\n'
        "}\n"
        "Constraints:\n"
        "- make outputs copy-ready\n"
        "- keep titles concise and high intent\n"
        "- keep hashtags relevant and non-spammy\n"
        "- keep thumbnail_text under 4 words each\n"
        "- if a section is less relevant for platform, still return an empty array instead of omitting it\n"
    )
    return system_prompt, user_prompt


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise RuntimeError("AI model returned empty content")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("AI model did not return valid JSON")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("AI model returned malformed JSON") from exc


def _normalize_ai_result(raw_payload: dict[str, Any], topic: str, platform: str, content_format: str) -> dict[str, Any]:
    titles = _dedupe_case_insensitive([str(item).strip() for item in raw_payload.get("titles", [])], limit=8)
    hashtags = _dedupe_case_insensitive([str(item).strip() for item in raw_payload.get("hashtags", [])], limit=15)
    seo_tags = _dedupe_case_insensitive([str(item).strip() for item in raw_payload.get("seo_tags", [])], limit=20)
    thumbnail_text = _dedupe_case_insensitive([str(item).strip() for item in raw_payload.get("thumbnail_text", [])], limit=6)
    thumbnail_ideas = _dedupe_case_insensitive([str(item).strip() for item in raw_payload.get("thumbnail_ideas", [])], limit=6)

    return {
        "platform": platform,
        "topic": topic,
        "content_format": content_format,
        "titles": titles,
        "description": str(raw_payload.get("description", "")).strip(),
        "hashtags": [item if item.startswith("#") else f"#{item}" for item in hashtags],
        "seo_tags": seo_tags,
        "thumbnail_text": thumbnail_text,
        "thumbnail_ideas": thumbnail_ideas,
        "source": "ai-model",
        "research": {
            "competitors": [],
            "keyword_buckets": {"primary": [], "supporting": [], "broad": []},
        },
    }


def _generate_ai_candidate(
    topic: str,
    platform: str,
    content_format: str,
    competitors: list[CompetitorVideo],
    keyword_buckets: dict[str, list[str]],
) -> dict[str, Any] | None:
    api_key = _nvidia_api_key()
    if not api_key or OpenAI is None:
        return None

    system_prompt, user_prompt = _build_ai_prompt(
        topic=topic,
        platform=platform,
        content_format=content_format,
        competitors=competitors,
        keyword_buckets=keyword_buckets,
    )

    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=_nvidia_model_name(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            top_p=0.95,
            max_tokens=1400,
            frequency_penalty=0,
            presence_penalty=0,
        )
    except Exception as exc:
        raise RuntimeError(f"AI model request failed: {exc}") from exc

    content = completion.choices[0].message.content if completion.choices else ""
    payload = _extract_json_object(content or "")
    return _normalize_ai_result(payload, topic=topic, platform=platform, content_format=content_format)


def _quality_score_title(title: str, topic: str, output_rules: dict[str, Any]) -> int:
    return round(_title_quality_score(title, _topic_keywords(topic), output_rules) * 100)


def _quality_score_description(description: str, topic_keywords: list[str], output_rules: dict[str, Any]) -> int:
    desc_rules = output_rules.get("description_rules", {})
    max_length = int(desc_rules.get("max_length_chars", 500))
    length_score = 1.0 if 90 <= len(description) <= max_length else max(0.2, 1 - abs(len(description) - 220) / max_length)
    keyword_score = _safe_ratio(sum(1 for keyword in topic_keywords[:3] if keyword in description.lower()), min(3, max(len(topic_keywords), 1)))
    early_bonus = 0.2 if any(keyword in description.lower()[:120] for keyword in topic_keywords[:2]) else 0.0
    return round(min(1.0, (length_score * 0.55) + (keyword_score * 0.25) + early_bonus) * 100)


def _readability_metrics(text: str) -> dict[str, float]:
    clean_text = (text or "").strip()
    if not clean_text or textstat is None:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "readability_score": 0.0,
        }

    try:
        reading_ease = float(textstat.flesch_reading_ease(clean_text))
        grade_level = float(textstat.flesch_kincaid_grade(clean_text))
    except Exception:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "readability_score": 0.0,
        }

    normalized_reading = min(max(reading_ease, 0.0), 100.0)
    # Lower grade level is easier to read. Grade 6-10 is a good target range.
    grade_penalty = min(max((grade_level - 6.0) / 8.0, 0.0), 1.0)
    readability_score = max(0.0, min(100.0, (normalized_reading * 0.7) + ((1 - grade_penalty) * 30)))

    return {
        "flesch_reading_ease": round(reading_ease, 2),
        "flesch_kincaid_grade": round(grade_level, 2),
        "readability_score": round(readability_score, 2),
    }


def _quality_score_tag_group(tags: list[str], topic_keywords: list[str], min_count: int, max_count: int) -> int:
    if not tags:
        return 0
    count_score = 1.0 if min_count <= len(tags) <= max_count else max(0.2, 1 - abs(len(tags) - max_count) / max_count)
    relevance_score = _safe_ratio(
        sum(1 for tag in tags if set(_topic_keywords(tag)) & set(topic_keywords)),
        max(1, min(len(tags), 8)),
    )
    return round(min(1.0, (count_score * 0.45) + (relevance_score * 0.55)) * 100)


def _quality_score_thumbnail_text(items: list[str], topic_keywords: list[str]) -> int:
    if not items:
        return 0
    valid = 0
    relevant = 0
    for item in items:
        words = item.split()
        if 1 <= len(words) <= 4:
            valid += 1
        if set(_topic_keywords(item)) & set(topic_keywords):
            relevant += 1
    return round(min(1.0, (_safe_ratio(valid, len(items)) * 0.6) + (_safe_ratio(relevant, len(items)) * 0.4)) * 100)


def _attach_quality_scores(result: dict[str, Any], output_rules: dict[str, Any]) -> dict[str, Any]:
    topic_keywords = _topic_keywords(result.get("topic", ""))
    hashtag_rules = output_rules.get("hashtag_rules", {})
    seo_tag_rules = output_rules.get("seo_tag_rules", {})
    best_title = result.get("titles", [])[0] if result.get("titles") else ""
    title_readability = _readability_metrics(best_title)
    description_readability = _readability_metrics(result.get("description", ""))

    title_scores = [
        {"title": title, "score": _quality_score_title(title, result.get("topic", ""), output_rules)}
        for title in result.get("titles", [])
    ]
    description_score = _quality_score_description(result.get("description", ""), topic_keywords, output_rules)
    hashtag_score = _quality_score_tag_group(
        result.get("hashtags", []),
        topic_keywords,
        int(hashtag_rules.get("min_count", 8)),
        int(hashtag_rules.get("max_count", 12)),
    )
    seo_tag_score = _quality_score_tag_group(
        result.get("seo_tags", []),
        topic_keywords,
        int(seo_tag_rules.get("min_count", 10)),
        int(seo_tag_rules.get("max_count", 20)),
    )
    thumbnail_text_score = _quality_score_thumbnail_text(result.get("thumbnail_text", []), topic_keywords)

    overall = round(
        (
            (title_scores[0]["score"] if title_scores else 0) * 0.3
            + description_score * 0.2
            + hashtag_score * 0.15
            + seo_tag_score * 0.2
            + thumbnail_text_score * 0.15
        )
    )

    result["quality_scores"] = {
        "titles": title_scores,
        "best_title_score": title_scores[0]["score"] if title_scores else 0,
        "title_readability": title_readability,
        "description_score": description_score,
        "description_readability": description_readability,
        "hashtags_score": hashtag_score,
        "seo_tags_score": seo_tag_score,
        "thumbnail_text_score": thumbnail_text_score,
        "overall_score": overall,
    }
    result["validation"] = {
        "passed": overall >= 70,
        "checks": {
            "best_title": (title_scores[0]["score"] if title_scores else 0) >= 70,
            "description": description_score >= 65,
            "title_readability": title_readability["readability_score"] >= 45,
            "description_readability": description_readability["readability_score"] >= 45,
            "hashtags": hashtag_score >= 65,
            "seo_tags": seo_tag_score >= 65,
            "thumbnail_text": thumbnail_text_score >= 60,
        },
    }
    return result


def _select_best_result(candidates: list[dict[str, Any]], output_rules: dict[str, Any]) -> dict[str, Any]:
    scored_candidates = []
    for candidate in candidates:
        scored_candidates.append(_attach_quality_scores(candidate, output_rules))

    return max(
        scored_candidates,
        key=lambda item: (
            item.get("quality_scores", {}).get("overall_score", 0),
            item.get("quality_scores", {}).get("best_title_score", 0),
        ),
    )


def _select_candidates_with_meta(
    candidates: list[dict[str, Any]],
    output_rules: dict[str, Any],
    ai_error: str = "",
) -> dict[str, Any]:
    selected = _select_best_result(candidates, output_rules)
    scored_sources = {
        candidate.get("source", "unknown"): candidate.get("quality_scores", {}).get("overall_score", 0)
        for candidate in candidates
        if candidate.get("quality_scores")
    }
    selected["candidate_sources"] = [candidate.get("source", "unknown") for candidate in candidates]
    selected["selection_meta"] = {
        "selected_source": selected.get("source", "unknown"),
        "scores_by_source": scored_sources,
        "ai_candidate_generated": any(candidate.get("source") == "ai-model" for candidate in candidates),
        "ai_error": ai_error,
    }
    return selected


def _build_ai_fallback_candidate(
    topic: str,
    platform: str,
    content_format: str,
    local_response: dict[str, Any],
) -> dict[str, Any] | None:
    keyword_buckets = local_response.get("research", {}).get("keyword_buckets", {})
    competitors: list[CompetitorVideo] = []
    return _generate_ai_candidate(
        topic=topic,
        platform=platform,
        content_format=content_format,
        competitors=competitors,
        keyword_buckets=keyword_buckets,
    )


def _build_live_response(
    topic: str,
    rules: SocialRules,
    output_rules: dict[str, Any],
    platform: str,
    content_format: str,
    competitors: list[CompetitorVideo],
) -> dict[str, Any]:
    topic_keywords = _topic_keywords(topic)
    ranked = _rank_competitors(competitors, topic_keywords, output_rules)[:5]

    extraction_texts = []
    for video in ranked:
        extraction_texts.extend([video.title, video.description])
        extraction_texts.extend(video.tags)
    phrases = _extract_phrases(extraction_texts, limit=18)
    buckets = _bucket_keywords(phrases, topic_keywords, output_rules)

    titles = _generate_titles(topic, content_format, buckets["primary"] + buckets["supporting"], ranked, rules, output_rules)
    description = _generate_description(topic, buckets["primary"] + buckets["supporting"], ranked)
    hashtags = _generate_hashtags(topic, buckets["primary"] + buckets["supporting"], rules)
    seo_tags = _generate_seo_tags(topic, buckets["primary"] + buckets["supporting"] + buckets["broad"], ranked, output_rules)
    thumbnail_text = _generate_thumbnail_text(buckets["primary"] + buckets["supporting"], rules)
    thumbnail_ideas = _generate_thumbnail_ideas(topic, ranked, rules)

    deterministic_result = {
        "platform": rules.platform,
        "topic": topic,
        "content_format": content_format,
        "titles": titles,
        "description": description,
        "hashtags": hashtags,
        "seo_tags": seo_tags,
        "thumbnail_ideas": thumbnail_ideas,
        "thumbnail_text": thumbnail_text,
        "source": "youtube-live",
        "insights": {
            "sampled_videos": len(competitors),
            "sampled_channels": _dedupe_case_insensitive([video.channel for video in ranked], limit=5),
        },
        "research": {
            "keyword_buckets": buckets,
            "competitors": [
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "channel": video.channel,
                    "view_count": video.view_count,
                    "like_count": video.like_count,
                    "rank_score": round(video.rank_score * 100, 1),
                }
                for video in ranked
            ],
        },
    }
    ai_error = ""
    try:
        ai_candidate = _generate_ai_candidate(
            topic=topic,
            platform=platform,
            content_format=content_format,
            competitors=ranked,
            keyword_buckets=buckets,
        )
    except RuntimeError as exc:
        ai_candidate = None
        ai_error = str(exc)

    candidates = [deterministic_result]
    if ai_candidate is not None:
        ai_candidate["research"] = deterministic_result["research"]
        ai_candidate["insights"] = deterministic_result["insights"]
        candidates.append(ai_candidate)

    return _select_candidates_with_meta(candidates, output_rules, ai_error=ai_error)


def generate_seo_content(
    topic: str,
    platform: str = "youtube",
    prefer_live: bool = True,
    youtube_api_key: str = "",
    use_env_fallback: bool = True,
    content_format: str = "long",
) -> dict:
    clean_topic = (topic or "").strip()
    if not clean_topic:
        raise ValueError("Topic is required")

    clean_platform = (platform or "youtube").strip().lower()
    normalized_format = _normalize_content_format(content_format)
    rules = _load_rules(clean_platform)
    output_rules = _load_output_rules()

    local_response = _build_local_response(
        topic=clean_topic,
        rules=rules,
        content_format=normalized_format,
        output_rules=output_rules,
    )

    def _finalize_fallback_response(live_error: str = "") -> dict[str, Any]:
        fallback_response = dict(local_response)
        fallback_response["source"] = "local-rules"
        if live_error:
            fallback_response["live_error"] = live_error

        ai_error = ""
        candidates = [fallback_response]
        try:
            ai_candidate = _build_ai_fallback_candidate(
                topic=clean_topic,
                platform=clean_platform,
                content_format=normalized_format,
                local_response=fallback_response,
            )
        except RuntimeError as exc:
            ai_candidate = None
            ai_error = str(exc)

        if ai_candidate is not None:
            ai_candidate["research"] = fallback_response.get("research", {})
            candidates.append(ai_candidate)

        return _select_candidates_with_meta(candidates, output_rules, ai_error=ai_error)

    if clean_platform != "youtube" or not prefer_live:
        return _finalize_fallback_response()

    try:
        competitors = _fetch_youtube_competitors(
            topic=clean_topic,
            content_format=normalized_format,
            api_key=youtube_api_key,
            use_env_fallback=use_env_fallback,
        )
        if not competitors:
            return _finalize_fallback_response("No videos returned from YouTube API")

        return _build_live_response(
            topic=clean_topic,
            rules=rules,
            output_rules=output_rules,
            platform=clean_platform,
            content_format=normalized_format,
            competitors=competitors,
        )
    except RuntimeError as exc:
        return _finalize_fallback_response(str(exc))

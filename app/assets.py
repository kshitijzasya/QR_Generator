from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import re


FETCH_TIMEOUT_SECONDS = 10
MAX_HTML_BYTES = 1_500_000
MAX_INLINE_SNIPPET_LENGTH = 800

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_space(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip())


def _safe_int(value: int | float, lower: int = 0, upper: int = 100) -> int:
    return max(lower, min(upper, round(value)))


def _clip_text(value: str, limit: int = MAX_INLINE_SNIPPET_LENGTH) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _resolved_url(raw_url: str, base_url: str) -> str:
    candidate = (raw_url or "").strip()
    if not candidate:
        return ""
    return urljoin(base_url, candidate) if base_url else candidate


def _guess_asset_kind(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".js"):
        return "script"
    if path.endswith(".css"):
        return "stylesheet"
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")):
        return "image"
    if path.endswith((".woff", ".woff2", ".ttf", ".otf")):
        return "font"
    return "other"


@dataclass
class PageStats:
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    lang: str = ""
    viewport: bool = False
    robots: str = ""
    h1_count: int = 0
    h2_count: int = 0
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    script_urls: list[str] = field(default_factory=list)
    stylesheet_urls: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    font_urls: list[str] = field(default_factory=list)
    other_asset_urls: list[str] = field(default_factory=list)
    preload_urls: list[str] = field(default_factory=list)
    inline_scripts: list[str] = field(default_factory=list)
    inline_styles: list[str] = field(default_factory=list)
    image_alts_missing: int = 0
    lazy_images: int = 0


class _PageParser(HTMLParser):
    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stats = PageStats()
        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._capture_h1 = False
        self._capture_h2 = False
        self._text_parts: list[str] = []
        self._inline_script_parts: list[str] = []
        self._inline_style_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()

        if lowered_tag == "html":
            self.stats.lang = attrs_map.get("lang", "").strip()
        elif lowered_tag == "title":
            self._in_title = True
        elif lowered_tag == "meta":
            name = attrs_map.get("name", "").strip().lower()
            prop = attrs_map.get("property", "").strip().lower()
            content = attrs_map.get("content", "").strip()
            if name == "description" and not self.stats.meta_description:
                self.stats.meta_description = _normalize_space(content)
            if name == "robots" and not self.stats.robots:
                self.stats.robots = _normalize_space(content)
            if name == "viewport":
                self.stats.viewport = True
            if prop == "og:title" and not self.stats.title:
                self.stats.title = _normalize_space(content)
        elif lowered_tag == "link":
            rel_tokens = {item.strip().lower() for item in attrs_map.get("rel", "").split() if item.strip()}
            href = _resolved_url(attrs_map.get("href", ""), self.base_url)
            as_value = attrs_map.get("as", "").strip().lower()
            if "canonical" in rel_tokens and href and not self.stats.canonical:
                self.stats.canonical = href
            if "stylesheet" in rel_tokens and href:
                self.stats.stylesheet_urls.append(href)
            elif ("preload" in rel_tokens or "modulepreload" in rel_tokens) and href:
                self.stats.preload_urls.append(href)
                kind = as_value or _guess_asset_kind(href)
                self._store_misc_asset(href, kind)
            elif href:
                self._store_misc_asset(href, _guess_asset_kind(href))
        elif lowered_tag == "script":
            src = _resolved_url(attrs_map.get("src", ""), self.base_url)
            if src:
                self.stats.script_urls.append(src)
            else:
                self._in_script = True
                self._inline_script_parts = []
        elif lowered_tag == "style":
            self._in_style = True
            self._inline_style_parts = []
        elif lowered_tag == "img":
            src = _resolved_url(attrs_map.get("src", ""), self.base_url)
            if src:
                self.stats.image_urls.append(src)
            if not attrs_map.get("alt", "").strip():
                self.stats.image_alts_missing += 1
            if attrs_map.get("loading", "").strip().lower() == "lazy":
                self.stats.lazy_images += 1
        elif lowered_tag == "a":
            href = _resolved_url(attrs_map.get("href", ""), self.base_url)
            if not href.startswith(("http://", "https://")):
                self.stats.internal_links += 1
            elif self.base_url and urlparse(href).netloc == urlparse(self.base_url).netloc:
                self.stats.internal_links += 1
            elif href:
                self.stats.external_links += 1
        elif lowered_tag == "h1":
            self.stats.h1_count += 1
            self._capture_h1 = True
        elif lowered_tag == "h2":
            self.stats.h2_count += 1
            self._capture_h2 = True

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag == "title":
            self._in_title = False
        elif lowered_tag == "script":
            if self._in_script:
                snippet = _clip_text(_normalize_space("".join(self._inline_script_parts)))
                if snippet:
                    self.stats.inline_scripts.append(snippet)
            self._in_script = False
            self._inline_script_parts = []
        elif lowered_tag == "style":
            if self._in_style:
                snippet = _clip_text(_normalize_space("".join(self._inline_style_parts)))
                if snippet:
                    self.stats.inline_styles.append(snippet)
            self._in_style = False
            self._inline_style_parts = []
        elif lowered_tag == "h1":
            self._capture_h1 = False
        elif lowered_tag == "h2":
            self._capture_h2 = False

    def handle_data(self, data: str) -> None:
        text = _normalize_space(data)
        if not text:
            return
        if self._in_title and not self.stats.title:
            self.stats.title = text
        if self._in_script:
            self._inline_script_parts.append(data)
        elif self._in_style:
            self._inline_style_parts.append(data)
        else:
            self._text_parts.append(text)

    def close(self) -> None:
        super().close()
        all_text = " ".join(self._text_parts)
        self.stats.word_count = len(re.findall(r"\b[\w'-]+\b", all_text))
        self.stats.script_urls = _dedupe(self.stats.script_urls)
        self.stats.stylesheet_urls = _dedupe(self.stats.stylesheet_urls)
        self.stats.image_urls = _dedupe(self.stats.image_urls)
        self.stats.font_urls = _dedupe(self.stats.font_urls)
        self.stats.other_asset_urls = _dedupe(self.stats.other_asset_urls)
        self.stats.preload_urls = _dedupe(self.stats.preload_urls)

    def _store_misc_asset(self, url: str, kind: str) -> None:
        if kind == "font":
            self.stats.font_urls.append(url)
        elif kind not in {"stylesheet", "script", "image"}:
            self.stats.other_asset_urls.append(url)


def _dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = (item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _fetch_url_html(target_url: str) -> tuple[str, dict[str, Any]]:
    normalized_url = (target_url or "").strip()
    if not normalized_url:
        raise ValueError("URL is required")
    if not normalized_url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    request = Request(
        normalized_url,
        headers={
            "User-Agent": "ZasyaAssetExtractor/1.0 (+https://zasyasolutions.com)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
            status = getattr(response, "status", 200)
            if "html" not in content_type.lower():
                raise ValueError("URL did not return an HTML document")
            html_bytes = response.read(MAX_HTML_BYTES + 1)
    except HTTPError as exc:
        raise RuntimeError(f"Could not fetch page: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not fetch page: {exc.reason}") from exc

    if len(html_bytes) > MAX_HTML_BYTES:
        raise ValueError("HTML document is too large to analyze")

    html = html_bytes.decode("utf-8", errors="replace")
    return html, {
        "final_url": final_url,
        "content_type": content_type,
        "http_status": status,
        "html_bytes": len(html_bytes),
    }


def _score_seo(stats: PageStats) -> tuple[int, list[dict[str, Any]]]:
    checks = [
        ("Title present", bool(stats.title), 15),
        ("Title length between 20 and 65 chars", 20 <= len(stats.title) <= 65, 10),
        ("Meta description present", bool(stats.meta_description), 15),
        ("Meta description length between 70 and 180 chars", 70 <= len(stats.meta_description) <= 180, 10),
        ("Single H1 present", stats.h1_count == 1, 12),
        ("At least one H2 present", stats.h2_count >= 1, 8),
        ("Viewport meta present", stats.viewport, 6),
        ("Canonical link present", bool(stats.canonical), 8),
        ("Document language declared", bool(stats.lang), 6),
        ("Images mostly have alt text", stats.image_alts_missing == 0 or len(stats.image_urls) == 0, 10),
    ]
    score = sum(weight for _label, passed, weight in checks if passed)
    return score, [{"label": label, "passed": passed, "weight": weight} for label, passed, weight in checks]


def _score_performance(stats: PageStats, html_size: int) -> tuple[int, list[dict[str, Any]]]:
    render_blocking = len(stats.stylesheet_urls) + len(stats.script_urls)
    image_count = len(stats.image_urls)
    inline_weight = sum(len(item) for item in stats.inline_scripts) + sum(len(item) for item in stats.inline_styles)
    lazy_ratio = 1.0 if image_count == 0 else stats.lazy_images / max(image_count, 1)

    checks = [
        ("HTML payload under 200 KB", html_size <= 200_000, 18),
        ("Fewer than 6 stylesheets", len(stats.stylesheet_urls) < 6, 14),
        ("Fewer than 10 external scripts", len(stats.script_urls) < 10, 14),
        ("Render-blocking assets under 12", render_blocking < 12, 14),
        ("Inline JS/CSS under 40 KB", inline_weight <= 40_000, 10),
        ("Fewer than 20 images", image_count < 20, 10),
        ("Most images use lazy loading", lazy_ratio >= 0.6 or image_count == 0, 10),
        ("Preload hints used", len(stats.preload_urls) >= 1, 10),
    ]
    score = sum(weight for _label, passed, weight in checks if passed)
    return score, [{"label": label, "passed": passed, "weight": weight} for label, passed, weight in checks]


def _build_findings(stats: PageStats, seo_score: int, performance_score: int) -> list[str]:
    findings: list[str] = []
    if not stats.title:
        findings.append("Missing page title.")
    if not stats.meta_description:
        findings.append("Missing meta description.")
    if stats.h1_count == 0:
        findings.append("No H1 heading detected.")
    elif stats.h1_count > 1:
        findings.append("Multiple H1 headings detected.")
    if stats.image_alts_missing:
        findings.append(f"{stats.image_alts_missing} image(s) are missing alt text.")
    if len(stats.stylesheet_urls) >= 6:
        findings.append("High stylesheet count may increase render blocking.")
    if len(stats.script_urls) >= 10:
        findings.append("High external script count may slow first render.")
    if len(stats.image_urls) >= 20:
        findings.append("Large image count may hurt loading performance.")
    if not stats.preload_urls:
        findings.append("No preload hints detected for critical assets.")
    if seo_score >= 80 and performance_score >= 80:
        findings.append("Page structure looks healthy based on heuristic checks.")
    return findings


def _summarize_assets(stats: PageStats) -> dict[str, Any]:
    return {
        "scripts": {
            "count": len(stats.script_urls),
            "urls": stats.script_urls,
            "inline_snippets": stats.inline_scripts[:5],
        },
        "stylesheets": {
            "count": len(stats.stylesheet_urls),
            "urls": stats.stylesheet_urls,
            "inline_snippets": stats.inline_styles[:5],
        },
        "images": {
            "count": len(stats.image_urls),
            "urls": stats.image_urls,
            "missing_alt_count": stats.image_alts_missing,
            "lazy_loaded_count": stats.lazy_images,
        },
        "fonts": {
            "count": len(stats.font_urls),
            "urls": stats.font_urls,
        },
        "preloads": {
            "count": len(stats.preload_urls),
            "urls": stats.preload_urls,
        },
        "other": {
            "count": len(stats.other_asset_urls),
            "urls": stats.other_asset_urls,
        },
    }


def analyze_page_assets(url: str = "", html: str = "", base_url: str = "") -> dict[str, Any]:
    raw_html = (html or "").strip()
    raw_url = (url or "").strip()
    raw_base_url = (base_url or "").strip()

    if not raw_html and not raw_url:
        raise ValueError("Provide either html or url")

    fetch_meta = {
        "source": "html",
        "final_url": raw_base_url,
        "content_type": "text/html; charset=utf-8",
        "http_status": None,
        "html_bytes": len(raw_html.encode("utf-8")),
    }

    if raw_url and not raw_html:
        raw_html, fetched = _fetch_url_html(raw_url)
        fetch_meta = {"source": "url", **fetched}
        raw_base_url = fetched.get("final_url", raw_url)

    parser = _PageParser(base_url=raw_base_url or raw_url)
    parser.feed(raw_html)
    parser.close()
    stats = parser.stats

    seo_score, seo_checks = _score_seo(stats)
    performance_score, performance_checks = _score_performance(stats, fetch_meta["html_bytes"])
    overall_score = _safe_int((seo_score * 0.55) + (performance_score * 0.45))

    return {
        "input": {
            "mode": "url" if fetch_meta["source"] == "url" else "html",
            "url": raw_url,
            "base_url": raw_base_url,
        },
        "fetch": fetch_meta,
        "page": {
            "title": stats.title,
            "meta_description": stats.meta_description,
            "canonical": stats.canonical,
            "lang": stats.lang,
            "robots": stats.robots,
            "word_count": stats.word_count,
            "h1_count": stats.h1_count,
            "h2_count": stats.h2_count,
            "internal_links": stats.internal_links,
            "external_links": stats.external_links,
            "html_source": raw_html,
            "html_preview": _clip_text(raw_html, limit=1200),
        },
        "scores": {
            "overall": overall_score,
            "seo": seo_score,
            "performance": performance_score,
            "seo_checks": seo_checks,
            "performance_checks": performance_checks,
            "note": "Scores are heuristic estimates based on extracted markup and asset structure, not Lighthouse/Core Web Vitals.",
        },
        "assets": _summarize_assets(stats),
        "findings": _build_findings(stats, seo_score, performance_score),
    }

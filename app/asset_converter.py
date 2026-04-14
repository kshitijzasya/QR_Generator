from __future__ import annotations

import json
import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


SUPPORTED_TARGET_STACKS = {
    "react",
    "nextjs",
    "vue",
    "nuxt",
    "svelte",
    "html",
}


def _nvidia_api_key() -> str:
    return (os.getenv("NVIDIA_CODE_API_KEY") or os.getenv("NVIDIA_API_KEY") or "").strip()


def _nvidia_model_name() -> str:
    return (os.getenv("NVIDIA_CODE_MODEL_NAME") or os.getenv("NVIDIA_MODEL_NAME") or "nvidia/nemotron-3-super-120b-a12b").strip()


def _build_ai_messages(html: str, target_stack: str, notes: str) -> list[dict[str, str]]:
    system_prompt = (
        "You convert existing page HTML into clean component code for the requested frontend stack. "
        "Preserve the page structure and semantic hierarchy. Keep the output copy-paste ready. "
        "Return JSON with keys: file_name, language, output."
    )
    user_prompt = (
        f"Target stack: {target_stack}\n"
        f"Extra notes: {notes or 'none'}\n"
        "Convert this page structure into the requested stack. "
        "Keep external assets as references when possible and avoid inventing backend logic.\n\n"
        f"HTML:\n{html}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _safe_json_extract(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None


def _fallback_file_name(target_stack: str) -> str:
    mapping = {
        "react": "ConvertedPage.jsx",
        "nextjs": "page.jsx",
        "vue": "ConvertedPage.vue",
        "nuxt": "pages/index.vue",
        "svelte": "ConvertedPage.svelte",
        "html": "converted-page.html",
    }
    return mapping.get(target_stack, "ConvertedPage.txt")


def _fallback_language(target_stack: str) -> str:
    if target_stack in {"react", "nextjs"}:
        return "jsx"
    if target_stack in {"vue", "nuxt"}:
        return "vue"
    if target_stack == "svelte":
        return "svelte"
    return "html"


def _render_fallback_conversion(html: str, target_stack: str) -> str:
    escaped_html = json.dumps(html)

    if target_stack == "react":
        return (
            "export default function ConvertedPage() {\n"
            f"  const markup = {escaped_html};\n\n"
            "  return <main dangerouslySetInnerHTML={{ __html: markup }} />;\n"
            "}\n"
        )
    if target_stack == "nextjs":
        return (
            "export default function Page() {\n"
            f"  const markup = {escaped_html};\n\n"
            "  return <main dangerouslySetInnerHTML={{ __html: markup }} />;\n"
            "}\n"
        )
    if target_stack == "vue":
        return (
            "<script setup>\n"
            f"const markup = {escaped_html};\n"
            "</script>\n\n"
            "<template>\n"
            "  <main v-html=\"markup\"></main>\n"
            "</template>\n"
        )
    if target_stack == "nuxt":
        return (
            "<script setup>\n"
            f"const markup = {escaped_html};\n"
            "</script>\n\n"
            "<template>\n"
            "  <main v-html=\"markup\"></main>\n"
            "</template>\n"
        )
    if target_stack == "svelte":
        return (
            "<script>\n"
            f"  const markup = {escaped_html};\n"
            "</script>\n\n"
            "<main>\n"
            "  {@html markup}\n"
            "</main>\n"
        )
    return html


def convert_page_structure(html: str, target_stack: str, notes: str = "") -> dict[str, Any]:
    clean_html = (html or "").strip()
    clean_target = (target_stack or "").strip().lower()
    clean_notes = (notes or "").strip()

    if not clean_html:
        raise ValueError("HTML is required for conversion")
    if clean_target not in SUPPORTED_TARGET_STACKS:
        raise ValueError("Unsupported target stack")

    api_key = _nvidia_api_key()
    if api_key and OpenAI is not None:
        client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
        try:
            completion = client.chat.completions.create(
                model=_nvidia_model_name(),
                messages=_build_ai_messages(clean_html, clean_target, clean_notes),
                temperature=0.2,
                top_p=0.9,
                max_tokens=1800,
            )
            content = completion.choices[0].message.content if completion.choices else ""
            payload = _safe_json_extract(content or "")
            if payload and payload.get("output"):
                return {
                    "target_stack": clean_target,
                    "file_name": str(payload.get("file_name") or _fallback_file_name(clean_target)),
                    "language": str(payload.get("language") or _fallback_language(clean_target)),
                    "output": str(payload.get("output") or "").strip(),
                    "source": "ai-model",
                }
        except Exception:
            pass

    return {
        "target_stack": clean_target,
        "file_name": _fallback_file_name(clean_target),
        "language": _fallback_language(clean_target),
        "output": _render_fallback_conversion(clean_html, clean_target),
        "source": "deterministic-fallback",
    }

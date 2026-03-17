import os
import time
from uuid import uuid4

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


CODE_CONVERSATION_TIMEOUT_SECONDS = 300
CODE_CONVERSATIONS: dict[str, dict] = {}


def _nvidia_api_key() -> str:
    return (os.getenv("NVIDIA_CODE_API_KEY") or "").strip() 

def _nvidia_model_name() -> str:
    return (os.getenv("NVIDIA_CODE_MODEL_NAME") or "nvidia/nemotron-3-super-120b-a12b").strip()


def _prune_expired_conversations(now: float | None = None) -> None:
    current_time = now if now is not None else time.time()
    expired_ids = [
        conversation_id
        for conversation_id, payload in CODE_CONVERSATIONS.items()
        if current_time - float(payload.get("last_activity_at", 0)) > CODE_CONVERSATION_TIMEOUT_SECONDS
    ]
    for conversation_id in expired_ids:
        CODE_CONVERSATIONS.pop(conversation_id, None)


def _resolve_conversation(
    conversation_id: str = "",
    fresh_conversation: bool = False,
    now: float | None = None,
) -> tuple[str, list[dict[str, str]], bool, bool]:
    current_time = now if now is not None else time.time()
    _prune_expired_conversations(current_time)

    normalized_id = (conversation_id or "").strip()
    if fresh_conversation:
        normalized_id = ""

    conversation_expired = bool(conversation_id) and normalized_id not in CODE_CONVERSATIONS
    if conversation_expired:
        normalized_id = ""

    if not normalized_id:
        new_id = uuid4().hex
        CODE_CONVERSATIONS[new_id] = {"messages": [], "last_activity_at": current_time}
        return new_id, [], True, conversation_expired

    payload = CODE_CONVERSATIONS.setdefault(normalized_id, {"messages": [], "last_activity_at": current_time})
    return normalized_id, list(payload.get("messages", [])), False, conversation_expired


def _store_conversation_messages(conversation_id: str, messages: list[dict[str, str]], now: float | None = None) -> None:
    CODE_CONVERSATIONS[conversation_id] = {
        # Reverse slicing of the conversation to get only last 12 parts
        "messages": messages[-12:],
        "last_activity_at": now if now is not None else time.time(),
    }


def _build_code_system_prompt(language: str, framework: str) -> str:
    return (
        "You are a pragmatic coding assistant. Maintain continuity across the conversation, "
        "keep answers grounded in the existing request history, and avoid random topic jumps. "
        f"Current target language: {language or 'unspecified'}. "
        f"Current framework or runtime: {framework or 'unspecified'}. "
        "When the user asks follow-up questions, continue from the existing code context instead of restarting."
    )


def generate_code_content(
    prompt: str,
    framework: str,
    language: str,
    conversation_id: str = "",
    fresh_conversation: bool = False,
):
    api_key=_nvidia_api_key()
    model_name=_nvidia_model_name()
    if not api_key or model_name is None:
        return None

    resolved_conversation_id, prior_messages, is_fresh_conversation, conversation_expired = _resolve_conversation(
        conversation_id=conversation_id,
        fresh_conversation=fresh_conversation,
    )

    messages = [
        {
            "role": "system",
            "content": _build_code_system_prompt(language=language, framework=framework),
        },
        *prior_messages,
        {"role": "user", "content": prompt.strip()},
    ]

    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=1,
            top_p=0.95,
            max_tokens=513,
            stream=True,
            extra_body={"chat_template_kwargs":{"enable_thinking":True},"reasoning_budget":16384}
        )
    except Exception as exc:
        raise RuntimeError(f"AI model request failed: {exc}") from exc

    chunks: list[str] = []
    for chunk in completion:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and getattr(delta, "content", None):
            chunks.append(delta.content)

    content = "".join(chunks).strip()
    if not content:
        raise RuntimeError("AI model returned empty content")

    stored_messages = prior_messages + [
        {"role": "user", "content": prompt.strip()},
        {"role": "assistant", "content": content},
    ]
    _store_conversation_messages(resolved_conversation_id, stored_messages)
    
    return {
        "prompt": prompt,
        "framework": framework,
        "language": language,
        "content": content,
        "source": "ai-model",
        "conversation_id": resolved_conversation_id,
        "is_fresh_conversation": is_fresh_conversation,
        "conversation_expired": conversation_expired,
        "conversation_timeout_seconds": CODE_CONVERSATION_TIMEOUT_SECONDS,
    }

import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _nvidia_api_key() -> str:
    return (os.getenv("NVIDIA_CODE_API_KEY") or "").strip() 

def _nvidia_model_name() -> str:
    return (os.getenv("NVIDIA_CODE_MODEL_NAME") or "nvidia/nemotron-3-super-120b-a12b").strip()

def generate_code_content(prompt: str, framework: str, language: str):
    api_key=_nvidia_api_key()
    model_name=_nvidia_model_name()
    if not api_key or model_name is None:
        return None
    
    user_prompt=f"{prompt} and where language is {language} and framework for the language is {framework}. Give me short quick and relative answer to this."

    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
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
    
    return {
        "prompt": prompt,
        "framework": framework,
        "language": language,
        "content": content,
        "source": "ai-model",
    }

import json
import re
import time
from typing import Any, Iterable, cast

from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
from openai.types.chat import ChatCompletionMessageParam

from app.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key or "placeholder_key",
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
            max_retries=0,  # we handle retries ourselves
        )
    return _client


def chat(
    messages: Iterable[ChatCompletionMessageParam] | list[dict[str, Any]],
    model: str | None = None,
    json_mode: bool = False,
    temperature: float | None = None,
) -> str:
    """Chat completion with retry + backoff on rate limits/timeouts."""
    client = get_client()
    model_name = model or settings.llm_model
    temp = settings.llm_temperature if temperature is None else temperature
    typed_messages = cast(Iterable[ChatCompletionMessageParam], messages)

    for attempt in range(settings.llm_max_retries + 1):
        try:
            if json_mode:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=typed_messages,
                    temperature=temp,
                    response_format={"type": "json_object"},
                )
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=typed_messages,
                    temperature=temp,
                )
            return response.choices[0].message.content or ""
        except (RateLimitError, APITimeoutError, APIConnectionError):
            if attempt == settings.llm_max_retries:
                raise
            time.sleep(2 ** attempt * 2)  # 2s, 4s, ...
    return ""


def chat_json(
    messages: Iterable[ChatCompletionMessageParam] | list[dict[str, Any]],
    model: str | None = None,
) -> dict:
    """Chat that must return JSON. Retries once on bad JSON."""
    curr_messages: list[ChatCompletionMessageParam] = list(
        cast(Iterable[ChatCompletionMessageParam], messages)
    )
    for attempt in range(2):
        text = chat(curr_messages, model=model, json_mode=True, temperature=0.0)
        cleaned = text.strip()
        code_fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
        candidate = code_fence.group(1) if code_fence else re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.DOTALL).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Fallback: extract substring between first { and last }
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(candidate[start:end + 1])
                except json.JSONDecodeError:
                    pass
            if attempt == 1:
                raise ValueError(f"LLM returned invalid JSON: {text[:200]}")
            curr_messages.append({"role": "user", "content": "Return ONLY valid JSON."})
    return {}
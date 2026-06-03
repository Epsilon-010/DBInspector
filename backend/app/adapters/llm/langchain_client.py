from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.adapters.llm._json_parsing import parse_json_object


class LangChainLLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._base = ChatAnthropic(
            api_key=api_key,
            model=model,
            max_tokens=1024,
            temperature=0.0,
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        chat = self._base.bind(max_tokens=max_tokens, temperature=temperature)
        message = await chat.ainvoke(
            [_cached_system(system), HumanMessage(content=user)]
        )
        return _extract_text(message.content)

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> dict:
        text = await self.complete(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return parse_json_object(text)


def _cached_system(system: str) -> SystemMessage:
    # cache_control marks the system block ephemeral so Anthropic reuses it across
    # calls within the 5-min TTL (~90% input-token discount on hits).
    block = {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
    return SystemMessage(content=[block])


def _extract_text(content: str | list) -> str:
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
        else:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()

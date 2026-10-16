from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import config
from agent.state import AgentState


def _strip_code_fence(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"```(?:markdown|md)?\s*([\s\S]*?)```", value, flags=re.IGNORECASE)
    return match.group(1).strip() if match else value


def _looks_like_markdown(value: str) -> bool:
    if not value or len(value.strip()) < 20:
        return False
    text = value.strip()
    return bool(re.search(r"(^|\n)#{1,6}\s+\S+", text) or re.search(r"\n\s*\n", text) or len(text.split()) >= 8)


def _similarity_score(original: str, rewritten: str) -> float:
    """Measure structural/textual overlap to catch superficial rewrites."""
    original_text = re.sub(r"\s+", "", original).lower()
    rewritten_text = re.sub(r"\s+", "", rewritten).lower()
    if not original_text or not rewritten_text:
        return 1.0
    return SequenceMatcher(None, original_text, rewritten_text, autojunk=False).ratio()


def _is_deep_rewrite(original: str, rewritten: str) -> bool:
    if not _looks_like_markdown(rewritten):
        return False
    similarity = _similarity_score(original, rewritten)
    original_head = re.sub(r"\s+", "", original[:220]).lower()
    rewritten_head = re.sub(r"\s+", "", rewritten[:220]).lower()
    same_opening = SequenceMatcher(None, original_head, rewritten_head, autojunk=False).ratio() >= 0.72
    original_headings = re.findall(r"(?m)^#{1,6}\s+(.+)$", original)
    rewritten_headings = re.findall(r"(?m)^#{1,6}\s+(.+)$", rewritten)
    heading_overlap = len(set(original_headings) & set(rewritten_headings)) / max(1, len(set(original_headings)))
    return similarity < 0.72 and not same_opening and heading_overlap < 0.7


def _friendly_rewrite_error(exc: Exception) -> str:
    """Convert provider/network exceptions into actionable user-facing text."""
    raw = str(exc).strip()
    detail = raw.lower()
    if "connection" in detail or "connecterror" in detail:
        return "文字改写服务暂时无法连接，已保留原文。请检查模型接口地址和网络后重试。"
    if "timed out" in detail or "timeout" in detail:
        return "文字改写服务响应超时，已保留原文。请稍后重试或缩短文章内容。"
    if "401" in detail or "unauthorized" in detail or "api key" in detail:
        return "文字改写服务鉴权失败，已保留原文。请检查 API Key 配置。"
    if "404" in detail or "not found" in detail or "model" in detail and "does not exist" in detail:
        return "文字改写模型不可用，已保留原文。请检查模型名称和接口地址。"
    return "文字改写未完成，已保留原文。请检查模型配置后重试。"


async def _invoke_llm(content: str, prompt_template: str | None = None, draft: str = "") -> str:
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 langchain-openai，无法执行文字改写") from exc

    if not config.OPENAI_API_KEY:
        raise RuntimeError("未配置 OPENAI_API_KEY，已回退到原文")
    kwargs: dict[str, Any] = {
        "model": config.REWRITE_MODEL,
        "temperature": config.REWRITE_TEMPERATURE,
        "max_tokens": config.REWRITE_MAX_TOKENS,
        "api_key": config.OPENAI_API_KEY,
        "timeout": config.LLM_TIMEOUT_SECONDS,
        "max_retries": config.LLM_MAX_RETRIES,
    }
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    model = ChatOpenAI(**kwargs)
    template = prompt_template or config.REWRITE_PROMPT
    prompt = template.format(content=content, draft=draft)
    messages = [
        SystemMessage(content="你负责对已获授权的文章做深度原创化编辑，必须保留事实准确性、必要来源和版权信息。禁止只做同义词替换。"),
        HumanMessage(content=prompt),
    ]
    response = await model.ainvoke(messages)
    value = response.content
    if isinstance(value, list):
        value = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in value)
    return str(value)


async def rewrite_node(state: AgentState) -> dict:
    """Rewrite text when configured; otherwise preserve it with a clear warning."""
    original = state.get("content_markdown") or ""
    errors = list(state.get("errors", []))
    if not original:
        error = "没有可改写的正文"
        errors.append(error)
        return {"rewritten_markdown": "", "rewrite_error": error, "errors": errors, "status": "running"}
    try:
        rewritten = _strip_code_fence(await _invoke_llm(original))
        if not _looks_like_markdown(rewritten):
            raise ValueError("模型返回为空或不是有效 Markdown")

        if not _is_deep_rewrite(original, rewritten):
            deep_prompt = getattr(config, "DEEP_REWRITE_PROMPT", config.REWRITE_PROMPT)
            deep_rewritten = _strip_code_fence(await _invoke_llm(original, deep_prompt, rewritten))
            if not _looks_like_markdown(deep_rewritten):
                raise ValueError("第二轮模型返回为空或不是有效 Markdown")
            rewritten = deep_rewritten
            if not _is_deep_rewrite(original, rewritten):
                errors.append("改写结果仍可能与原文存在较高相似度，建议人工复核")
            else:
                errors.append("首次改写相似度偏高，已自动执行第二轮深度重写")

        return {"rewritten_markdown": rewritten, "rewrite_error": None, "errors": errors, "status": "running"}
    except Exception as exc:
        error = _friendly_rewrite_error(exc)
        errors.append(error)
        return {
            "rewritten_markdown": original,
            "rewrite_error": error,
            "errors": errors,
            "status": "running",
        }

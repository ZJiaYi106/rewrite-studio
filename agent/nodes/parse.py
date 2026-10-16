from __future__ import annotations

from agent.state import AgentState
from agent.tools.wechat_crawl import crawl_wechat_article
import config


async def parse_node(state: AgentState) -> dict:
    """Fetch an authorized article and normalize its text/images."""
    if not state.get("authorized"):
        error = "未确认内容处理授权"
        errors = list(state.get("errors", [])) + [error]
        return {"parse_error": error, "status": "failed", "errors": errors}
    parse_dir = state.get("work_dir") or str(config.TEMP_DIR / "parsed")
    result = await crawl_wechat_article(state["url"], parse_dir)
    errors = list(state.get("errors", []))
    parse_error = result.get("error")
    warning = result.get("image_warning")
    if warning:
        errors.append(warning)
    if parse_error:
        errors.append(parse_error)
    if not result.get("markdown"):
        parse_error = parse_error or "解析结果为空：页面中没有可处理的正文"
        errors.append(parse_error) if parse_error not in errors else None
        return {
            "article_title": result.get("title"),
            "content_markdown": None,
            "images_dir": result.get("images_dir"),
            "image_paths": result.get("images", []),
            "parse_error": parse_error,
            "status": "failed",
            "errors": errors,
        }
    return {
        "article_title": result.get("title"),
        "content_markdown": result["markdown"],
        "images_dir": result.get("images_dir"),
        "image_paths": result.get("images", []),
        "image_failures": result.get("image_failures", []),
        "needs_manual_image_review": bool(result.get("image_failures")),
        "parse_error": None,
        "status": "running",
        "errors": errors,
    }

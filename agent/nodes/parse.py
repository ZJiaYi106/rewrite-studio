from __future__ import annotations

from agent.state import AgentState
from agent.tools.wechat_crawl import crawl_wechat_article
from agent.tools.document_parser import parse_document
import config


async def parse_node(state: AgentState) -> dict:
    """解析内容源：支持公众号 URL 或上传的文档"""
    if not state.get("authorized"):
        error = "未确认内容处理授权"
        errors = list(state.get("errors", [])) + [error]
        return {"parse_error": error, "status": "failed", "errors": errors}
    
    parse_dir = state.get("work_dir") or str(config.TEMP_DIR / "parsed")
    
    # 判断是 URL 还是文档路径
    source = state.get("url") or state.get("document_path")
    if not source:
        error = "未提供内容源（URL 或文档路径）"
        return {"parse_error": error, "status": "failed", "errors": [error]}
    
    # 根据类型选择解析方式
    if state.get("document_path"):
        # 文档解析模式
        result = await parse_document(state["document_path"], parse_dir)
    else:
        # 公众号抓取模式
        result = await crawl_wechat_article(state["url"], parse_dir)
    
    errors = list(state.get("errors", []))
    parse_error = result.get("error")
    warning = result.get("image_warning")
    if warning:
        errors.append(warning)
    if parse_error:
        errors.append(parse_error)
    if not result.get("markdown"):
        parse_error = parse_error or "解析结果为空：没有可处理的正文"
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

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """State passed between LangGraph nodes.

    The workflow is intended for content the caller owns or is authorized to
    transform. Optional fields make partial failures observable without
    interrupting later, non-dependent nodes.
    """

    url: Optional[str]  # 公众号 URL（可选）
    document_path: Optional[str]  # 上传文档路径（可选）
    authorized: bool
    work_dir: Optional[str]
    image_strategy: Optional[str]
    article_title: Optional[str]
    content_markdown: Optional[str]
    images_dir: Optional[str]
    image_paths: Optional[List[str]]
    parse_error: Optional[str]

    rewritten_markdown: Optional[str]
    rewrite_error: Optional[str]

    image_mapping: dict[str, str]
    image_slots: List[str]
    processed_images: Optional[List[str]]
    image_error: Optional[str]
    image_failures: List[str]
    needs_manual_image_review: bool

    output_dir: Optional[str]
    final_path: Optional[str]
    status: Literal["running", "completed", "failed"]
    errors: List[str]

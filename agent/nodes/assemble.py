from __future__ import annotations

import re
import shutil
from pathlib import Path

import config
from agent.state import AgentState


def _rewrite_image_paths(markdown: str, image_names: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix, path, suffix = match.groups()
        name = Path(path).name
        return f"{prefix}images/{name}{suffix}" if name in image_names else match.group(0)

    return re.sub(r"(!\[[^\]]*\]\()([^\)]+)(\))", replace, markdown)


async def assemble_node(state: AgentState) -> dict:
    """Write the final Markdown and copy successfully processed images."""
    output_dir = Path(state.get("work_dir") or config.BASE_OUTPUT_DIR) / "output"
    image_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    original_markdown = state.get("content_markdown") or ""
    markdown = state.get("rewritten_markdown") or original_markdown
    processed = state.get("processed_images") or []
    image_names: set[str] = set()
    for source_name in processed:
        source = Path(source_name)
        if not source.exists():
            continue
        target = image_dir / source.name
        shutil.copy2(source, target)
        image_names.add(target.name)

    mapping = state.get("image_mapping") or {}
    image_slots = list(state.get("image_slots") or [])
    replacement_index = 0

    def replace_rewritten_image(match: re.Match[str]) -> str:
        nonlocal replacement_index
        prefix, path, suffix = match.groups()
        original_name = Path(path).name
        if state.get("image_strategy") == "regenerate":
            if replacement_index >= len(image_slots):
                return ""
            target_name = image_slots[replacement_index]
            replacement_index += 1
        else:
            target_name = mapping.get(original_name, original_name)
        return f"{prefix}images/{target_name}{suffix}" if target_name in image_names else match.group(0)

    # In regenerate mode, keep at most IMAGE_REGENERATE_COUNT image slots in the final draft.
    markdown = re.sub(r"(!\[[^\]]*\]\()([^\)]+)(\))", replace_rewritten_image, markdown)
    markdown = _rewrite_image_paths(markdown, image_names)
    failures = state.get("image_failures") or []
    notes: list[str] = []
    if state.get("rewrite_error"):
        notes.append(f"<!-- 文字处理备注：{state['rewrite_error']} -->")
    if failures:
        notes.append(f"<!-- 图片处理失败清单：{', '.join(failures)} -->")
    if state.get("needs_manual_image_review"):
        notes.append("<!-- needs_manual_image_review: true -->")
    if notes:
        markdown = markdown.rstrip() + "\n\n" + "\n".join(notes) + "\n"

    final_path = output_dir / "article.md"
    final_path.write_text(markdown, encoding="utf-8")
    # Rewrite original.md to use the same images/ directory
    original_markdown = _rewrite_image_paths(original_markdown, image_names)
    original_path = output_dir / "original.md"
    original_path.write_text(original_markdown, encoding="utf-8")
    errors = list(state.get("errors", []))
    return {
        "output_dir": str(output_dir),
        "final_path": str(final_path),
        "status": "completed",
        "errors": errors,
    }

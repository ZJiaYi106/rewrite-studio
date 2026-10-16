from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from PIL import Image, ImageOps

import config
from agent.state import AgentState


async def _copy_or_edit(source: Path, target: Path, strategy: str) -> None:
    def process() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if strategy == "light_edit":
            # Keep dimensions and existing attribution/watermarks; only normalize orientation.
            with Image.open(source) as image:
                normalized = ImageOps.exif_transpose(image)
                if normalized.mode not in {"RGB", "RGBA"}:
                    normalized = normalized.convert("RGB")
                normalized.save(target)
        else:
            shutil.copy2(source, target)

    await asyncio.wait_for(asyncio.to_thread(process), timeout=config.IMAGE_TIMEOUT_SECONDS)


async def image_process_node(state: AgentState) -> dict:
    """Keep source images intact; regenerate only a small thematic image set."""
    paths = state.get("image_paths") or []
    strategy = (state.get("image_strategy") or config.IMAGE_STRATEGY).strip().lower()
    errors = list(state.get("errors", []))
    failures: list[str] = list(state.get("image_failures") or [])
    processed: list[str] = []
    output_dir = Path(state.get("work_dir") or config.TEMP_DIR) / "processed_images"
    output_dir.mkdir(parents=True, exist_ok=True)

    if strategy not in {"skip", "light_edit", "regenerate"}:
        message = f"未知图片策略 {strategy!r}，已使用 skip"
        errors.append(message)
        strategy = "skip"

    image_mapping: dict[str, str] = {}
    image_slots: list[str] = []

    if strategy == "regenerate":
        from agent.tools.image_gen import generate_image_from_description
        count = min(config.IMAGE_REGENERATE_COUNT, 5)
        prompts = [
            "文章主视觉：用编辑重新策划的方式概括文章主题，适合公众号头图，画面干净，有明确主体，不出现文字、Logo、水印或可识别品牌。",
            "文章场景配图：把文章讨论的问题放进一个真实、具体、有叙事感的生活或工作场景，适合公众号插图，不出现文字、Logo、水印。",
            "文章概念配图：用有创意但易理解的视觉隐喻表达文章核心观点，现代编辑插画风格，不出现文字、Logo、水印。",
            "文章行动配图：表现读者执行文章建议时的积极场景，真实自然，适合内容配图，不出现文字、Logo、水印。",
            "文章收束配图：用有余味的画面总结文章主题，构图简洁、色彩统一，适合公众号结尾配图，不出现文字、Logo、水印。",
        ]
        theme = state.get("article_title") or "一篇关于内容与实践的文章"
        for index in range(count):
            slot_name = f"slot_{index + 1:03d}.png"
            source = Path(paths[index]) if index < len(paths) else None
            try:
                prompt = f"文章主题：{theme}。{prompts[index]} 允许自由发挥，不需要参考原文图片。"
                generated = await generate_image_from_description(
                    prompt, f"theme_{index + 1}", str(output_dir), f"theme_{index + 1:03d}.png"
                )
                processed.append(generated)
                image_slots.append(Path(generated).name)
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else f"请求或图片处理异常（{type(exc).__name__}）"
                errors.append(f"第 {index + 1} 张主题配图生成失败：{message}")
                failures.append(f"theme_{index + 1:03d}.png")
                # Do not fall back to the source image in regenerate mode.
                # The rewritten draft must contain AI-generated images only.
        image_error = f"{len(failures)} 张图片生成失败" if failures else None
        return {
            "processed_images": processed,
            "image_slots": image_slots,
            "image_mapping": image_mapping,
            "image_error": image_error,
            "image_failures": failures,
            "needs_manual_image_review": bool(failures),
            "errors": errors,
            "status": "running",
        }

    for source_name in paths:
        source = Path(source_name)
        target = output_dir / source.name
        try:
            await _copy_or_edit(source, target, strategy)
            processed.append(str(target))
        except Exception as exc:
            failures.append(source.name)
            message = str(exc) if isinstance(exc, ValueError) else f"请求或图片处理异常（{type(exc).__name__}）"
            errors.append(f"图片处理失败 {source.name}：{message}，已保留原图")
            if source.is_file():
                fallback = output_dir / source.name
                try:
                    if source.resolve() != fallback.resolve():
                        await asyncio.to_thread(shutil.copy2, source, fallback)
                    processed.append(str(fallback))
                except Exception as fallback_exc:
                    failures.append(source.name)
                    errors.append(f"原图回退复制也失败 {source.name}：{type(fallback_exc).__name__}")

    image_error = f"{len(failures)} 张图片处理失败" if failures else None
    return {
        "processed_images": processed,
        "image_mapping": image_mapping,
        "image_error": image_error,
        "image_failures": failures,
        "needs_manual_image_review": bool(failures),
        "errors": errors,
        "status": "running",
    }

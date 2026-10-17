from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

import config
from agent.graph import build_graph


WEB_DIR = Path(__file__).resolve().parent
JOBS_ROOT = config.TEMP_DIR / "jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)


STEPS = [
    {"id": "parse", "label": "抓取文章", "detail": "读取正文、标题与图片"},
    {"id": "rewrite", "label": "重写内容", "detail": "保留事实，调整表达风格"},
    {"id": "process_images", "label": "处理图片", "detail": "复制、规范化或 AI 重新生成素材"},
    {"id": "assemble", "label": "组装成品", "detail": "生成 Markdown 与图片目录"},
]


class CreateJobRequest(BaseModel):
    url: HttpUrl
    authorized: bool = Field(..., description="用户确认拥有版权或已获明确授权")
    image_strategy: Literal["skip", "light_edit", "regenerate"] = "skip"


class CreateJobFromFileRequest(BaseModel):
    authorized: bool = Field(..., description="用户确认拥有版权或已获明确授权")
    image_strategy: Literal["skip", "light_edit", "regenerate"] = "skip"
    image_strategy: Literal["skip", "light_edit", "regenerate"] = "skip"


@dataclass
class Job:
    id: str
    image_strategy: str
    work_dir: Path
    url: str | None = None
    document_path: str | None = None
    status: str = "queued"
    current_step: str = "queued"
    title: str | None = None
    output_dir: str | None = None
    final_path: str | None = None
    original_path: str | None = None
    rewritten_path: str | None = None
    errors: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    current_action: str = "等待任务启动"
    current_detail: str = "任务创建后，这里会显示当前正在执行的具体工作。"
    step_started_at: float | None = None
    started_at: float | None = None
    finished_at: float | None = None
    task: asyncio.Task | None = None


jobs: dict[str, Job] = {}
app = FastAPI(title="Rewrite Studio", version="0.1.0")


def _safe_job_path(job: Job, relative_path: str) -> Path:
    root = job.work_dir.resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="非法文件路径")
    return target


def _step_status(job: Job, step_id: str) -> str:
    order = [step["id"] for step in STEPS]
    if job.status == "failed" and step_id == job.current_step:
        return "failed"
    if job.current_step == "completed":
        return "done"
    if step_id == job.current_step:
        return "active"
    try:
        return "done" if order.index(step_id) < order.index(job.current_step) else "pending"
    except ValueError:
        return "pending"


def _now() -> float:
    import time

    return time.time()


def _add_event(job: Job, message: str, kind: str = "info") -> None:
    job.events.append({"time": _now(), "message": message, "kind": kind})
    job.events = job.events[-30:]


def _set_step(job: Job, step_id: str, action: str, detail: str) -> None:
    job.current_step = step_id
    job.current_action = action
    job.current_detail = detail
    job.step_started_at = _now()
    _add_event(job, f"{action}：{detail}")


def _snapshot(job: Job) -> dict[str, Any]:
    now = _now()
    elapsed = max(0, now - job.started_at) if job.started_at else 0
    return {
        "id": job.id,
        "status": job.status,
        "current_step": job.current_step,
        "current_action": job.current_action,
        "current_detail": job.current_detail,
        "step_elapsed_seconds": max(0, now - job.step_started_at) if job.step_started_at else 0,
        "elapsed_seconds": elapsed,
        "title": job.title,
        "url": job.url or "(文档上传)",
        "image_strategy": job.image_strategy,
        "output_dir": job.output_dir,
        "final_path": job.final_path,
        "has_preview": bool(job.original_path and job.rewritten_path),
        "errors": job.errors[-10:],
        "events": job.events[-20:],
        "stats": job.stats,
        "steps": [{**step, "status": _step_status(job, step["id"])} for step in STEPS],
    }


async def _run_job(job: Job) -> None:
    import time

    job.status = "running"
    job.started_at = time.time()
    _set_step(job, "parse", "正在解析内容", "解析文章内容、标题、正文结构和图片。")
    state: dict[str, Any] = {
        "url": job.url or "(文档上传)",
        "document_path": job.document_path,
        "authorized": True,
        "work_dir": str(job.work_dir),
        "image_strategy": job.image_strategy,
        "status": "running",
        "errors": [],
        "image_failures": [],
        "needs_manual_image_review": False,
    }
    try:
        graph = build_graph()
        final = dict(state)
        async with asyncio.timeout(config.WEB_JOB_TIMEOUT_SECONDS):
            async for event in graph.astream(state):
                for node_name, node_state in event.items():
                    final.update(node_state)
                    if node_state.get("article_title"):
                        job.title = node_state["article_title"]
                    if node_name == "parse":
                        article = node_state.get("content_markdown") or ""
                        images = node_state.get("image_paths") or []
                        job.stats.update({"content_chars": len(article), "image_count": len(images)})
                        _set_step(job, "rewrite", "正在改写正文", f"已解析 {len(article):,} 个字符和 {len(images)} 张图片，正在等待模型输出新的 Markdown。")
                    elif node_name == "rewrite":
                        rewritten = node_state.get("rewritten_markdown") or ""
                        job.stats["rewritten_chars"] = len(rewritten)
                        _set_step(job, "process_images", "正在处理图片", f"正文已完成深度重写，输出 {len(rewritten):,} 个字符，正在处理 {job.stats.get('image_count', 0)} 张图片。")
                    elif node_name == "process_images":
                        processed = node_state.get("processed_images") or []
                        failures = node_state.get("image_failures") or []
                        job.stats.update({"processed_images": len(processed), "failed_images": len(failures)})
                        _set_step(job, "assemble", "正在组装成品", f"图片处理完成：成功 {len(processed)} 张，失败 {len(failures)} 张，正在写入输出目录。")
                    elif node_name == "assemble":
                        _set_step(job, "completed", "处理完成", "Markdown 和图片目录已经生成，可以下载成品。")
                    for error in node_state.get("errors", []):
                        if error not in job.errors:
                            job.errors.append(error)
        job.status = final.get("status", "failed")
        job.current_step = "completed" if job.status == "completed" else "failed"
        job.title = final.get("article_title") or job.title
        job.output_dir = final.get("output_dir")
        job.final_path = final.get("final_path")
        if job.status == "completed":
            output_root = Path(job.output_dir or "")
            original_path = output_root / "original.md"
            rewritten_path = Path(job.final_path or "")
            if original_path.is_file() and rewritten_path.is_file():
                job.original_path = str(original_path)
                job.rewritten_path = str(rewritten_path)
        if job.status == "completed":
            job.current_step = "completed"
            job.current_action = "处理完成"
            job.current_detail = "Markdown 和图片目录已经生成，可以下载成品。"
            _add_event(job, job.current_detail, "success")
        for error in final.get("errors", []):
            if error not in job.errors:
                job.errors.append(error)
    except TimeoutError:
        job.status = "failed"
        job.current_step = "failed"
        job.current_action = "任务达到安全上限"
        job.current_detail = f"任务超过 {int(config.WEB_JOB_TIMEOUT_SECONDS // 60)} 分钟仍未完成，已停止等待。"
        job.errors.append(f"任务超过 {int(config.WEB_JOB_TIMEOUT_SECONDS)} 秒仍未完成，请稍后重试")
        _add_event(job, job.current_detail, "error")
    except Exception as exc:
        job.status = "failed"
        job.current_step = "failed"
        job.current_action = "任务执行失败"
        job.current_detail = str(exc)
        job.errors.append(f"任务执行失败：{exc}")
        _add_event(job, f"任务执行失败：{exc}", "error")
    finally:
        job.finished_at = time.time()
        _cleanup_intermediate_files(job)

def _cleanup_intermediate_files(job: Job) -> None:
    """Clean up intermediate files after job completion to save disk space.
    
    Keeps:
    - output/ directory (final article.md and images/)
    
    Removes:
    - parsed/ directory (original downloaded images)
    - processed_images/ directory (intermediate processing results)
    - original_images/ directory (backup copies for preview)
    - ZIP archives from package downloads
    """
    try:
        cleanup_targets = [
            job.work_dir / "parsed",
            job.work_dir / "processed_images",
        ]
        
        if job.output_dir:
            output_root = Path(job.output_dir)
            cleanup_targets.append(output_root / "original_images")
        
        for target in cleanup_targets:
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
        
        for zip_file in job.work_dir.glob("rewrite-*.zip"):
            zip_file.unlink(missing_ok=True)
        
        _add_event(job, "已清理中间文件，节省磁盘空间", "info")
    except Exception as exc:
        _add_event(job, f"清理中间文件时出现异常（不影响任务结果）：{exc}", "warning")


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/static.css")
async def stylesheet() -> FileResponse:
    return FileResponse(WEB_DIR / "static.css", media_type="text/css")


@app.get("/app.js")
async def javascript() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js", media_type="text/javascript")


@app.post("/api/jobs", status_code=202)
async def create_job(payload: CreateJobRequest) -> dict[str, Any]:
    if not payload.authorized:
        raise HTTPException(status_code=400, detail="请先确认你拥有内容版权或已获明确授权")
    job_id = uuid.uuid4().hex[:12]
    work_dir = JOBS_ROOT / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    job = Job(id=job_id, url=str(payload.url), image_strategy=payload.image_strategy, work_dir=work_dir)
    jobs[job_id] = job
    job.task = asyncio.create_task(_run_job(job))
    return _snapshot(job)




@app.post("/api/jobs/upload", status_code=202)
async def create_job_from_file(
    file: UploadFile = File(...),
    authorized: bool = Form(..., description="用户确认拥有版权或已获明确授权"),
    image_strategy: str = Form("skip")
) -> dict[str, Any]:
    """上传文档并创建处理任务
    
    支持的文件格式：
    - PDF (.pdf)
    - Word 文档 (.docx, .doc)
    - 纯文本 (.txt)
    - Markdown (.md, .markdown)
    """
    if not authorized:
        raise HTTPException(status_code=400, detail="请先确认你拥有内容版权或已获明确授权")
    
    # 验证文件格式
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    suffix = Path(file.filename).suffix.lower()
    allowed_formats = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}
    if suffix not in allowed_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式 {suffix}，支持的格式：{', '.join(allowed_formats)}"
        )
    
    # 创建任务目录
    job_id = uuid.uuid4().hex[:12]
    work_dir = JOBS_ROOT / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存上传的文件
    upload_dir = work_dir / "upload"
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / file.filename
    
    try:
        content = await file.read()
        file_path.write_bytes(content)
    except Exception as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"文件保存失败：{exc}")
    
    # 创建任务
    job = Job(
        id=job_id, 
        url=None,  # 文档上传模式没有 URL
        document_path=str(file_path),
        image_strategy=image_strategy, 
        work_dir=work_dir
    )
    jobs[job_id] = job
    job.task = asyncio.create_task(_run_job(job))
    return _snapshot(job)

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return _snapshot(job)


@app.get("/api/jobs/{job_id}/preview")
async def get_job_preview(job_id: str) -> dict[str, str]:
    job = jobs.get(job_id)
    if job is None or not job.original_path or not job.rewritten_path:
        raise HTTPException(status_code=404, detail="文章对照预览尚未生成")
    original = Path(job.original_path)
    rewritten = Path(job.rewritten_path)
    if not original.is_file() or not rewritten.is_file():
        raise HTTPException(status_code=404, detail="预览文件不存在")
    return {
        "original_markdown": original.read_text(encoding="utf-8"),
        "rewritten_markdown": rewritten.read_text(encoding="utf-8"),
    }


@app.get("/api/jobs/{job_id}/article")
async def get_article(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if job is None or not job.final_path:
        raise HTTPException(status_code=404, detail="文章尚未生成")
    path = Path(job.final_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文章文件不存在")
    return FileResponse(path, media_type="text/markdown", filename="article.md")


@app.get("/api/jobs/{job_id}/package")
async def get_package(job_id: str) -> FileResponse:
    """Download article.md together with images so relative Markdown links work."""
    job = jobs.get(job_id)
    if job is None or not job.output_dir:
        raise HTTPException(status_code=404, detail="成品尚未生成")
    root = Path(job.output_dir)
    article = root / "article.md"
    images = root / "images"
    if not article.is_file():
        raise HTTPException(status_code=404, detail="文章文件不存在")
    archive_base = job.work_dir / f"rewrite-{job.id}"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=root))
    return FileResponse(archive_path, media_type="application/zip", filename=f"rewrite-{job.id}.zip")


@app.get("/api/jobs/{job_id}/files/{file_path:path}")
async def get_job_file(job_id: str, file_path: str) -> FileResponse:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    path = _safe_job_path(job, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
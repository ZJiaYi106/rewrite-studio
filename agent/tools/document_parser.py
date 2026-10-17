from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import config


async def parse_document(file_path: str, work_dir: str) -> dict[str, Any]:
    """解析上传的文档（PDF、DOCX、TXT、Markdown）
    
    Args:
        file_path: 上传文件的路径
        work_dir: 工作目录
        
    Returns:
        包含 title, markdown, images, error 的字典
    """
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        return {"error": f"文件不存在: {file_path}"}
    
    suffix = file_path_obj.suffix.lower()
    
    try:
        if suffix == ".pdf":
            return await _parse_pdf(file_path_obj, work_dir)
        elif suffix in {".docx", ".doc"}:
            return await _parse_docx(file_path_obj, work_dir)
        elif suffix in {".txt", ".md", ".markdown"}:
            return await _parse_text(file_path_obj, work_dir)
        else:
            return {"error": f"不支持的文件格式: {suffix}"}
    except Exception as exc:
        return {"error": f"文档解析失败: {type(exc).__name__} - {exc}"}


async def _parse_pdf(file_path: Path, work_dir: str) -> dict[str, Any]:
    """解析 PDF 文件"""
    try:
        import pdfplumber
        from PIL import Image
        import io
    except ImportError:
        return {"error": "缺少 PDF 解析依赖，请安装: pip install pdfplumber Pillow"}
    
    work_dir_path = Path(work_dir)
    images_dir = work_dir_path / "parsed" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    title = file_path.stem
    content_parts = []
    image_paths = []
    image_counter = 0
    
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # 提取文本
            text = page.extract_text()
            if text:
                content_parts.append(text.strip())
            
            # 提取图片
            if hasattr(page, 'images'):
                for img_info in page.images:
                    try:
                        image_counter += 1
                        img_name = f"image_{image_counter:03d}.png"
                        img_path = images_dir / img_name
                        
                        # 从 PDF 提取图片并保存
                        # 注意: pdfplumber 的图片提取比较复杂，这里提供基础实现
                        # 实际项目可能需要使用 PyMuPDF (fitz) 获得更好的图片提取
                        
                        image_paths.append(str(img_path))
                        content_parts.append(f"![图片](images/{img_name})")
                    except Exception as e:
                        continue
    
    markdown = "\n\n".join(content_parts)
    
    return {
        "title": title,
        "markdown": markdown,
        "images": image_paths,
        "images_dir": str(images_dir),
        "image_failures": [],
    }


async def _parse_docx(file_path: Path, work_dir: str) -> dict[str, Any]:
    """解析 DOCX 文件"""
    try:
        from docx import Document
        from docx.oxml.text.paragraph import CT_P
        from docx.oxml.table import CT_Tbl
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        return {"error": "缺少 DOCX 解析依赖，请安装: pip install python-docx"}
    
    work_dir_path = Path(work_dir)
    images_dir = work_dir_path / "parsed" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    doc = Document(file_path)
    title = file_path.stem
    content_parts = []
    image_paths = []
    image_counter = 0
    
    # 提取段落和图片
    for element in doc.element.body:
        if isinstance(element, CT_P):
            para = Paragraph(element, doc)
            text = para.text.strip()
            
            # 检查是否是标题
            if para.style.name.startswith('Heading'):
                level = int(para.style.name.replace('Heading ', ''))
                content_parts.append(f"{'#' * level} {text}")
            elif text:
                content_parts.append(text)
            
            # 提取段落中的图片
            for run in para.runs:
                if hasattr(run, '_element'):
                    for drawing in run._element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                        try:
                            image_counter += 1
                            img_name = f"image_{image_counter:03d}.png"
                            img_path = images_dir / img_name
                            
                            # 提取图片（简化版，实际需要更复杂的处理）
                            image_paths.append(str(img_path))
                            content_parts.append(f"![图片](images/{img_name})")
                        except Exception:
                            continue
        
        elif isinstance(element, CT_Tbl):
            # 简单的表格处理
            table = Table(element, doc)
            table_md = _table_to_markdown(table)
            if table_md:
                content_parts.append(table_md)
    
    markdown = "\n\n".join(content_parts)
    
    return {
        "title": title,
        "markdown": markdown,
        "images": image_paths,
        "images_dir": str(images_dir),
        "image_failures": [],
    }


def _table_to_markdown(table) -> str:
    """将 DOCX 表格转换为 Markdown"""
    rows = []
    for i, row in enumerate(table.rows):
        cells = [cell.text.strip() for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(rows)


async def _parse_text(file_path: Path, work_dir: str) -> dict[str, Any]:
    """解析纯文本或 Markdown 文件"""
    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding='gbk')
        except:
            return {"error": "无法读取文件编码"}
    
    title = file_path.stem
    
    # 如果是 Markdown，尝试提取一级标题作为 title
    first_line = content.split('\n')[0].strip()
    if first_line.startswith('# '):
        title = first_line[2:].strip()
    
    return {
        "title": title,
        "markdown": content,
        "images": [],
        "images_dir": None,
        "image_failures": [],
    }

from __future__ import annotations

import asyncio
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

import config


WECHAT_UA = (
    "Mozilla/5.0 (Linux; Android 13; PGT-AN00 Build/HUAWEIPGT-AN00) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/120.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.43"
)


def _safe_filename(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value[:80] or fallback


def _image_extension(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}:
        return suffix
    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0])
    return guessed if guessed in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} else ".jpg"


def _text_from_node(node: Tag) -> str:
    text = node.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def _inline_markdown(node: Any, image_map: dict[str, str]) -> str:
    if isinstance(node, NavigableString):
        return re.sub(r"\s+", " ", str(node))
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name == "br":
        return "\n"
    if name in {"strong", "b"}:
        return f"**{''.join(_inline_markdown(c, image_map) for c in node.children).strip()}**"
    if name in {"em", "i"}:
        return f"*{''.join(_inline_markdown(c, image_map) for c in node.children).strip()}*"
    if name == "a":
        label = "".join(_inline_markdown(c, image_map) for c in node.children).strip()
        href = (node.get("href") or "").strip()
        return f"[{label}]({href})" if href else label
    if name == "img":
        source = node.get("src") or node.get("data-src") or ""
        return f"![图片]({image_map[source]})" if source in image_map else ""
    return "".join(_inline_markdown(c, image_map) for c in node.children)


def _to_markdown(content: Tag, image_map: dict[str, str]) -> str:
    blocks: list[str] = []
    for child in content.children:
        if isinstance(child, NavigableString):
            text = re.sub(r"\s+", " ", str(child)).strip()
            if text:
                blocks.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower()
        if name in {"script", "style", "noscript"}:
            continue
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            blocks.append(f"{'#' * min(level, 6)} {_text_from_node(child)}")
        elif name in {"p", "section", "blockquote"}:
            text = _inline_markdown(child, image_map).strip()
            if text:
                blocks.append(text)
        elif name in {"ul", "ol"}:
            items = []
            for index, li in enumerate(child.find_all("li", recursive=False), 1):
                prefix = f"{index}." if name == "ol" else "-"
                items.append(f"{prefix} {_inline_markdown(li, image_map).strip()}")
            if items:
                blocks.append("\n".join(items))
        elif name == "img":
            image = _inline_markdown(child, image_map).strip()
            if image:
                blocks.append(image)
        else:
            text = _inline_markdown(child, image_map).strip()
            if text and (name in {"div", "article", "table"} or "\n" in text):
                blocks.append(text)
    return "\n\n".join(blocks).strip()


def _fetch_article(url: str, output_dir: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"title": "", "markdown": "", "images": [], "images_dir": "", "error": "请输入有效的 http(s) 公众号文章链接"}

    headers = {"User-Agent": WECHAT_UA, "Referer": "https://mp.weixin.qq.com/"}
    response = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    content = soup.select_one("#js_content")
    if content is None:
        return {"title": "", "markdown": "", "images": [], "images_dir": "", "error": "链接已过期或无效：页面中未找到 #js_content"}

    title_node = soup.select_one("#activity-name") or soup.select_one("h1")
    title = _text_from_node(title_node) if title_node else "未命名文章"
    article_dir = Path(output_dir)
    images_dir = article_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_map: dict[str, str] = {}
    image_paths: list[str] = []
    image_sources: list[str] = []

    for image in content.select("img"):
        source = (image.get("data-src") or image.get("src") or "").strip()
        if not source or source.startswith("data:"):
            continue
        absolute = urljoin(url, source)
        image_sources.append(source)
        try:
            image_response = requests.get(absolute, headers=headers, timeout=config.REQUEST_TIMEOUT_SECONDS)
            image_response.raise_for_status()
            index = len(image_paths) + 1
            extension = _image_extension(absolute, image_response.headers.get("Content-Type"))
            target = images_dir / f"img_{index:03d}{extension}"
            target.write_bytes(image_response.content)
            relative = f"images/{target.name}"
            image_map[source] = relative
            image_map[absolute] = relative
            image_paths.append(str(target))
        except requests.RequestException:
            continue

    markdown = _to_markdown(content, image_map)
    failed = len(image_sources) - len(image_paths)
    warning = None
    if image_sources and failed / len(image_sources) > 0.5:
        warning = f"图片下载失败 {failed}/{len(image_sources)}，已继续处理文字内容"
    return {
        "title": title,
        "markdown": markdown,
        "images": image_paths,
        "images_dir": str(images_dir),
        "image_warning": warning,
        "image_failures": [f"未下载图片 {index}" for index in range(1, failed + 1)],
        "error": None,
    }


async def crawl_wechat_article(url: str, output_dir: str) -> dict[str, Any]:
    """抓取经授权处理的公众号文章，并将图片保存到本地。"""
    try:
        return await asyncio.to_thread(_fetch_article, url, output_dir)
    except requests.RequestException as exc:
        return {"title": "", "markdown": "", "images": [], "images_dir": "", "error": f"文章请求失败：{exc}"}
    except Exception as exc:  # Keep the graph state serializable on unexpected HTML changes.
        return {"title": "", "markdown": "", "images": [], "images_dir": "", "error": f"文章解析失败：{exc}"}

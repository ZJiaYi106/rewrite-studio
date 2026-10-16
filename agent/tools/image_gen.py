from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path

import httpcore

import httpx
from PIL import Image, ImageOps

import config


def _endpoint(base: str, route: str) -> str:
    return base.rstrip('/') + '/' + route


def _headers(key: str | None) -> dict[str, str]:
    if not key:
        raise ValueError('未配置图片模型 API 密钥')
    return {'Authorization': 'Bearer ' + key}


def _check(response: httpx.Response, label: str) -> dict:
    # Do not expose provider response bodies: they may contain secrets or image bytes.
    if response.is_error:
        raise ValueError(f'{label}接口返回 HTTP {response.status_code}，请检查密钥、模型名及接口配置')
    try:
        return response.json()
    except ValueError as exc:
        raise ValueError(f'{label}接口返回了无法解析的响应') from exc


async def _post_with_retry(client: httpx.AsyncClient, url: str, *, headers: dict, json: dict, label: str) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return await client.post(url, headers=headers, json=json)
        except (httpx.RemoteProtocolError, httpx.ReadError, httpcore.RemoteProtocolError, httpcore.ReadError) as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise ValueError(f'{label}服务连接被远端中断，已重试 3 次；请稍后再试') from last_error


async def describe_image(image_path: str) -> str:
    """Encode only inside the request; return a description, never image bytes."""
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((1536, 1536))
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    payload = {
        'model': config.VLM_MODEL,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': '描述这张图片的主体、场景、构图、色彩和风格，写成重新创作公众号配图的提示词。不要编造事实，不要复刻标志、署名或水印。仅输出描述。'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + encoded}},
        ]}],
    }
    async with httpx.AsyncClient(timeout=config.VLM_TIMEOUT_SECONDS) as client:
        response = await _post_with_retry(
            client, _endpoint(config.VLM_BASE_URL, 'chat/completions'),
            headers=_headers(config.VLM_API_KEY), json=payload, label='图片理解'
        )
    data = _check(response, '图片理解')
    text = data['choices'][0]['message']['content']
    if not isinstance(text, str) or not text.strip():
        raise ValueError('图片理解模型未返回有效描述')
    return text.strip()


async def generate_image_from_description(description: str, original_path: str, output_dir: str, output_name: str | None = None) -> str:
    """Generate a thematic illustration; original_path is used only for naming."""
    payload = {'model': config.IMAGE_GEN_MODEL, 'prompt': description,
               'size': config.IMAGE_GEN_SIZE, 'n': 1}
    async with httpx.AsyncClient(timeout=config.IMAGE_GEN_TIMEOUT_SECONDS) as client:
        response = await _post_with_retry(
            client, _endpoint(config.IMAGE_GEN_BASE_URL, 'images/generations'),
            headers=_headers(config.IMAGE_GEN_API_KEY), json=payload, label='生图'
        )
        data = _check(response, '生图')
        items = data.get('data') or []
        if not items:
            raise ValueError('生图接口未返回图片')
        item = items[0]
        if item.get('b64_json'):
            raw = base64.b64decode(item['b64_json'], validate=True)
        elif item.get('url'):
            # Download without Authorization; never forward API keys to an image host.
            url = httpx.URL(item['url'])
            if url.scheme != 'https':
                raise ValueError('生图接口返回了非 HTTPS 图片地址')
            downloaded = await client.get(url)
            if downloaded.is_error:
                raise ValueError(f'生成图片下载失败 HTTP {downloaded.status_code}')
            raw = downloaded.content
        else:
            raise ValueError('生图响应缺少 url 或 b64_json')
    target = Path(output_dir) / (output_name or (Path(original_path).stem + '.png'))
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(raw)) as image:
        image.convert('RGBA').save(target, format='PNG')
    return str(target)

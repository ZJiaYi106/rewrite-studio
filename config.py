from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")
BASE_OUTPUT_DIR = Path(os.getenv("BASE_OUTPUT_DIR", ROOT_DIR / "output"))
TEMP_DIR = Path(os.getenv("TEMP_DIR", ROOT_DIR / "temp"))

# Models can be replaced by any OpenAI-compatible endpoint.
REWRITE_MODEL = os.getenv("REWRITE_MODEL", "gpt-4o-mini")
VLM_MODEL = os.getenv("VLM_MODEL") or "qwen-vl-plus"
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "dall-e-3")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Independent OpenAI-compatible image endpoints. Empty keys inherit the text key.
VLM_API_KEY = os.getenv("VLM_API_KEY") or OPENAI_API_KEY
VLM_BASE_URL = os.getenv("VLM_BASE_URL") or OPENAI_BASE_URL or "https://api.openai.com/v1"
VLM_TIMEOUT_SECONDS = float(os.getenv("VLM_TIMEOUT_SECONDS", "600"))
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY") or OPENAI_API_KEY
IMAGE_GEN_BASE_URL = os.getenv("IMAGE_GEN_BASE_URL") or OPENAI_BASE_URL or "https://api.openai.com/v1"
IMAGE_GEN_TIMEOUT_SECONDS = float(os.getenv("IMAGE_GEN_TIMEOUT_SECONDS", "600"))
IMAGE_GEN_SIZE = os.getenv("IMAGE_GEN_SIZE", "1024x1024")
IMAGE_REGENERATE_COUNT = max(3, min(5, int(os.getenv("IMAGE_REGENERATE_COUNT", "5"))))

# Keep the default conservative and deterministic: original images are copied.
IMAGE_STRATEGY = os.getenv("IMAGE_STRATEGY", "skip").strip().lower()
REWRITE_TEMPERATURE = float(os.getenv("REWRITE_TEMPERATURE", "0.85"))
REWRITE_MAX_TOKENS = int(os.getenv("REWRITE_MAX_TOKENS", "6000"))
# Long-running defaults: keep a generous safety ceiling for slow providers and large articles.
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))
IMAGE_TIMEOUT_SECONDS = float(os.getenv("IMAGE_TIMEOUT_SECONDS", "300"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))
WEB_JOB_TIMEOUT_SECONDS = float(os.getenv("WEB_JOB_TIMEOUT_SECONDS", "3600"))

REWRITE_PROMPT = """你是一名资深公众号主编。仅处理用户拥有或已获授权的内容。
你的任务不是同义词替换，也不是逐句润色，而是先理解原文要解决的问题和核心事实，再重新策划一篇有独立表达的文章。

请严格执行以下要求：
1. 先在心里提炼：文章主题、目标读者、核心事实、关键结论、可保留的案例和必要来源；不要把分析过程输出给用户。
2. 重新确定文章切入角度。开头必须重新写，不能沿用原文第一段的句式、叙事顺序或铺垫方式。
3. 重新设计标题和小标题体系。允许合并、拆分、调换原有章节，不要机械保留原文的小标题和章节顺序。
4. 全文重写话术、语气、句式和段落节奏。不要做“刚准备”改成“刚开始”这类低改写度替换。
5. 可以自由使用提问、场景化开头、对比、清单、案例拆解、行动步骤和总结，但不能虚构原文没有的事实、数据、人物经历或结论。
6. 保留核心事实、必要来源、版权信息、免责声明和图片位置；图片 Markdown 占位符必须保留，但可以调整它所在的段落位置。
7. 每段尽量控制在 40 至 100 字，长内容要主动拆段；避免连续多段使用原文相同的句式。
8. 删除无关推广尾巴、追踪链接和重复表达，补足自然的过渡句，让全文像重新写出来的一篇文章。
9. 改写后的文章应与原文在开头、标题、段落组织和句式上明显不同，而不是只改变几个词。
10. 只输出最终 Markdown，不输出分析、说明、改写理由或“以下是改写结果”等套话。

原文：
{content}"""

DEEP_REWRITE_PROMPT = """你需要对一篇已经改写但仍然过于接近原文的文章进行第二轮深度重写。
仅处理用户拥有或已获授权的内容。请把原文当作事实素材和研究笔记，重新完成一次公众号文章创作。

这次必须做到：
1. 换一个自然的开场，不得沿用原文或上一版的前两段表达。
2. 重做标题、小标题和全文结构，可以按“问题—判断—方法—行动”或其他更适合读者的顺序组织。
3. 大幅改写句式和叙述方式，避免逐句对应、同义词替换、原句扩写和原段落复刻。
4. 适度加入场景化表达、具体问题、反问、对比或清单，让文章更像一个编辑重新策划后的成稿。
5. 只保留原文可验证的事实、必要来源、版权信息、免责声明和图片 Markdown 占位符；绝不杜撰数字、人物、经历和引用。
6. 每段尽量 40 至 100 字，主动拆分过长段落，避免所有段落长度和节奏都与原文一致。
7. 只输出 Markdown 成稿，不解释你的过程，不提及“原文”“上一版”或本次重写。

素材原文：
{content}

上一版草稿（仅用于识别哪些表达不能继续沿用，不要照着改几个词）：
{draft}"""


def ensure_directories() -> None:
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

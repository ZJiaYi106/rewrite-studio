# Rewrite Studio

一个基于 Python + LangGraph 的公众号文章处理工作台，适用于用户自己拥有或已获明确授权处理的内容。当前流程为：抓取正文和图片 -> LLM 原创化编辑 -> 图片保守处理 -> 输出 Markdown 与图片目录。

## Web UI

安装依赖：

```bash
conda create -n wechat-rewrite-agent python=3.11 -y
conda activate wechat-rewrite-agent
pip install -r requirements.txt
```

配置项目根目录的 `.env`：

```env
OPENAI_API_KEY=你的模型密钥
OPENAI_BASE_URL=https://你的兼容接口/v1
REWRITE_MODEL=你的模型名称
IMAGE_STRATEGY=skip
```

启动 Web UI：

```bash
python run_web.py
```

浏览器打开：`http://127.0.0.1:8000`

Web API：

- `GET /api/health`：健康检查
- `POST /api/jobs`：创建处理任务
- `GET /api/jobs/{job_id}`：查询任务状态
- `GET /api/jobs/{job_id}/article`：下载 Markdown 成品
- `GET /api/jobs/{job_id}/files/{file_path}`：读取任务目录内的图片文件

Web 任务每次使用独立工作目录：`temp/jobs/{job_id}/`，避免多个任务互相覆盖。当前任务状态保存在进程内存中；公网部署前应接入持久化任务队列、数据库、用户认证、访问限流和对象存储。

## Docker 部署

服务器建议使用单容器、单 worker，并由现有 Nginx/Caddy 负责 HTTPS 和子域名转发。

首次部署：

```bash
cp .env.example .env
mkdir -p data/output data/temp
# 编辑 .env，填写模型密钥、接口地址和模型名称
HOST_PORT=18080 docker compose up -d --build
```

检查服务：

```bash
docker compose ps
docker compose logs -f rewrite-web
curl http://127.0.0.1:18080/api/health
```

Caddy 反向代理示例见 `Caddyfile.example`，将 `rewrite.example.com` 替换为实际子域名。Docker 容器内部使用 `PORT=8000`，宿主机默认使用 `127.0.0.1:18080`，避免和其他项目冲突。

更新部署：

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```

`.env` 不会复制进镜像；`data/output` 和 `data/temp` 会持久化到服务器目录。当前仍建议保持单 worker，因为任务状态存储在进程内存中。

## 命令行模式

```bash
python run.py "https://mp.weixin.qq.com/s/your-article-id"
```

## 当前策略

- `skip`：默认复制原图，不做内容重制。
- `light_edit`：使用 Pillow 做 EXIF 方向归一化，保留原始内容和署名信息。
- `regenerate`：当前仅保留接口并标记人工复核，不会自动生成替代图片。
- 没有模型密钥或模型异常时，文字节点会回退原文，组装流程仍会产出文件。
- 图片下载失败或处理失败会写入 `article.md` 末尾的 HTML 注释。

## 磁盘空间管理

项目已优化磁盘使用，任务完成后自动清理中间文件：

**保留文件：**
- `output/article.md`：最终改写文章
- `output/original.md`：原文备份（用于对比预览）
- `output/images/`：处理后的图片（article.md 和 original.md 共享）

**自动清理：**
- `parsed/`：抓取时下载的原始图片
- `processed_images/`：图片处理中间产物
- `rewrite-*.zip`：打包下载后的临时压缩包

**效果：** 单任务磁盘占用从 ~80MB 降至 ~4MB（节省 95%）

**清理历史任务：**

```bash
python tests/cleanup_historical.py --yes
```

检查清理状态：

```bash
python tests/test_cleanup.py
```

## 公网部署前清单

1. 使用 HTTPS，并把 `0.0.0.0:8000` 放在 Nginx / Caddy 反向代理之后。
2. 增加用户登录、任务归属校验、请求频率限制和最大正文长度限制。
3. 将任务队列从进程内 `asyncio` 替换为 Redis + Celery / RQ / Arq 等持久化方案。
4. 将输出文件迁移到对象存储，设置短期签名下载地址。
5. 日志中不要记录 API Key、完整文章正文或用户私密信息。
6. 只处理用户拥有版权或已取得明确授权的内容，并保留必要来源和署名信息。

## 后续完善顺序

1. `agent/tools/wechat_crawl.py`：增强复杂正文结构、表格、视频和媒体资源解析。
2. `agent/nodes/rewrite.py`：增加事实保留、敏感信息和长度校验。
3. `web/app.py`：接入认证、持久化任务状态和限流。
4. `agent/nodes/image.py` 与 `agent/tools/image_gen.py`：在明确授权与版权边界后接入 VLM / 文生图。
5. `tests/`：为 API、任务状态和失败回退补齐测试。
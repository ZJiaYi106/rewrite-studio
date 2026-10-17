# 文档上传功能 - 更新说明

## 新增功能

现在 Rewrite Studio 支持直接上传文档进行重写，无需公众号链接！

### 支持的文档格式

- **PDF** (`.pdf`) - 自动提取文本和图片
- **Word** (`.docx`, `.doc`) - 保留标题层级和表格
- **纯文本** (`.txt`) - 直接处理文本内容
- **Markdown** (`.md`, `.markdown`) - 保留 Markdown 格式

### 使用方式

#### 1. Web UI（推荐）

1. 访问 Web 界面
2. 切换到"上传文档"标签
3. 拖拽或点击选择文件
4. 配置图片处理策略
5. 确认版权授权
6. 开始处理

**支持拖拽上传**，体验更流畅！

#### 2. 命令行模式

```bash
# 处理 PDF 文档
python run.py document.pdf --file

# 处理 Word 文档
python run.py report.docx --file

# 交互式选择模式
python run.py
# 然后选择：2 (文档模式)
```

#### 3. API 调用

```bash
# 上传并处理文档
curl -X POST http://localhost:8000/api/jobs/upload \
  -F "file=@document.pdf" \
  -F "authorized=true" \
  -F "image_strategy=skip"

# 返回任务 ID，然后轮询状态
curl http://localhost:8000/api/jobs/{job_id}
```

### 技术实现

**新增文件：**
- `agent/tools/document_parser.py` - 文档解析工具
  - PDF 解析（使用 pdfplumber）
  - DOCX 解析（使用 python-docx）
  - 文本/Markdown 解析

**修改文件：**
- `agent/state.py` - 添加 `document_path` 字段
- `agent/nodes/parse.py` - 支持文档和 URL 两种输入
- `web/app.py` - 新增 `/api/jobs/upload` 接口
- `web/index.html` - 添加文件上传 UI
- `web/app.js` - 添加文件上传逻辑
- `run.py` - 命令行支持文档处理
- `requirements.txt` - 添加文档解析依赖

**新增依赖：**
- `pdfplumber>=0.10` - PDF 文本提取
- `python-docx>=1.0` - Word 文档处理

### 工作流程

```
上传文档 → 解析内容 → LLM 重写 → 图片处理 → 输出 Markdown
```

文档和公众号链接使用相同的重写流程，确保输出质量一致。

### 注意事项

1. **文件大小限制**：建议单个文件不超过 10MB
2. **PDF 图片提取**：复杂 PDF 的图片提取可能不完整
3. **Word 兼容性**：`.doc` 格式需要 python-docx 支持
4. **编码处理**：文本文件自动尝试 UTF-8 和 GBK 编码

### 应用场景

- 📄 处理会议纪要和报告
- 📚 改写学术论文和研究文档
- 📝 优化产品文档和使用手册
- 📋 重写培训材料和教程

### 后续计划

- [ ] 支持更多格式（RTF、ODT、HTML）
- [ ] 改进 PDF 图片提取质量
- [ ] 支持扫描 PDF 的 OCR 识别
- [ ] 批量文档处理

---

**更新日期：** 2026-10-17
**功能状态：** ✅ 已完成并测试

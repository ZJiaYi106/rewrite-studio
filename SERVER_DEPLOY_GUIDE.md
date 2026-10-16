# Rewrite Studio 服务器部署指南

## 步骤 1：SSH 连接到服务器

```bash
ssh your_user@your_server
```

## 步骤 2：克隆代码到 /opt/rewrite-studio

```bash
# 如果目录已存在，先备份
if [ -d "/opt/rewrite-studio" ]; then
    sudo mv /opt/rewrite-studio /opt/rewrite-studio-backup-$(date +%Y%m%d-%H%M%S)
fi

# 克隆代码
cd /opt
sudo git clone https://github.com/ZJiaYi106/rewrite-studio.git
sudo chown -R $(whoami):$(whoami) rewrite-studio
cd rewrite-studio
```

## 步骤 3：配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件（填写你的 API 密钥）
vim .env
# 或
nano .env
```

**必须配置的项目：**
```env
OPENAI_API_KEY=你的模型密钥
OPENAI_BASE_URL=https://你的兼容接口/v1
REWRITE_MODEL=你的模型名称
IMAGE_STRATEGY=skip
```

## 步骤 4：创建数据目录

```bash
mkdir -p data/output data/temp
```

## 步骤 5：启动 Docker 服务

```bash
# 停止旧服务（如果存在）
docker compose down

# 构建并启动
docker compose build
HOST_PORT=18080 docker compose up -d
```

## 步骤 6：验证部署

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f rewrite-web

# 测试 API（在新终端）
curl http://localhost:18080/api/health
```

如果返回 `{"status":"ok"}`，说明部署成功！

## 步骤 7：清理历史任务（可选）

```bash
docker compose exec rewrite-web python tests/cleanup_historical.py --yes
```

## 日常管理命令

```bash
# 查看日志
docker compose logs -f rewrite-web

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新代码
cd /opt/rewrite-studio
git pull origin main
docker compose up -d --build
```

## 如果需要配置 Caddy 反向代理

参考项目中的 `Caddyfile.example`，将 `rewrite.example.com` 替换为你的域名。

---

## 快速一键部署命令（复制粘贴）

如果 .env 已经配置好，可以直接运行：

```bash
ssh your_user@your_server << 'EOF'
cd /opt
sudo rm -rf rewrite-studio
sudo git clone https://github.com/ZJiaYi106/rewrite-studio.git
sudo chown -R $(whoami):$(whoami) rewrite-studio
cd rewrite-studio
# 确保 .env 已配置
mkdir -p data/output data/temp
docker compose down || true
docker compose build
HOST_PORT=18080 docker compose up -d
sleep 10
docker compose ps
curl -f http://localhost:18080/api/health && echo "✅ 部署成功" || echo "❌ 部署失败"
EOF
```

注意：首次部署前必须先配置 .env 文件！

#!/bin/bash
# 服务器部署脚本 - Rewrite Studio

set -e  # 遇到错误立即退出

echo "🚀 开始部署 Rewrite Studio..."

# 1. 进入目标目录
cd /opt/rewrite-studio

# 2. 备份现有代码（如果存在）
if [ -d ".git" ]; then
    echo "📦 检测到现有代码，创建备份..."
    BACKUP_DIR="/opt/rewrite-studio-backup-$(date +%Y%m%d-%H%M%S)"
    sudo cp -r /opt/rewrite-studio "$BACKUP_DIR"
    echo "✅ 备份已保存到: $BACKUP_DIR"
fi

# 3. 克隆或拉取代码
if [ ! -d ".git" ]; then
    echo "📥 首次克隆代码..."
    cd /opt
    sudo rm -rf rewrite-studio
    sudo git clone https://github.com/ZJiaYi106/rewrite-studio.git
    sudo chown -R $USER:$USER rewrite-studio
    cd rewrite-studio
else
    echo "🔄 更新现有代码..."
    git fetch origin
    git reset --hard origin/main
fi

# 4. 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，从示例创建..."
    cp .env.example .env
    echo "❗ 请编辑 .env 文件，填写 API 密钥和配置"
    echo "   vim .env"
    exit 1
else
    echo "✅ .env 文件已存在"
fi

# 5. 创建必要目录
mkdir -p data/output data/temp
echo "✅ 数据目录已创建"

# 6. 停止旧容器
if [ -f "docker-compose.yml" ]; then
    echo "🛑 停止现有服务..."
    docker compose down || true
fi

# 7. 构建并启动新容器
echo "🔨 构建 Docker 镜像..."
docker compose build

echo "🚀 启动服务..."
HOST_PORT=18080 docker compose up -d

# 8. 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 9. 检查服务状态
echo "🔍 检查服务状态..."
docker compose ps

# 10. 测试健康检查
echo "🏥 测试 API 健康检查..."
if curl -f http://localhost:18080/api/health > /dev/null 2>&1; then
    echo "✅ 服务运行正常！"
    echo ""
    echo "📊 服务信息："
    echo "  - 内部端口: 8000"
    echo "  - 宿主机端口: 18080"
    echo "  - 健康检查: http://localhost:18080/api/health"
    echo ""
    echo "📝 查看日志："
    echo "  docker compose logs -f rewrite-web"
    echo ""
    echo "🧹 清理历史任务（可选）："
    echo "  docker compose exec rewrite-web python tests/cleanup_historical.py --yes"
else
    echo "❌ 服务启动失败，查看日志："
    docker compose logs rewrite-web
    exit 1
fi

echo ""
echo "🎉 部署完成！"

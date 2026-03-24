# ===========================================
# 美亚航旅API MCP Server Dockerfile
# ===========================================

# 使用官方Python基础镜像
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖（优化构建缓存）
RUN pip install --no-cache-dir -r requirements.txt

# ===========================================
# 生产镜像
# ===========================================
FROM python:3.11-slim

WORKDIR /app

# 从builder复制依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ ./src/
COPY config/ ./config/

# 复制配置文件
COPY requirements.txt .
COPY pyproject.toml .

# 创建日志目录
RUN mkdir -p /app/logs

# 创建非root用户（安全）
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

# 暴露端口（HTTP模式）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 启动命令
CMD ["python", "-m", "src.server"]

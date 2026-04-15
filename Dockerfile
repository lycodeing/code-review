FROM python:3.12-slim AS base

WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制源码（hatchling 需要 src/ 来做 editable install）
COPY pyproject.toml README.md ./
COPY src/ src/
COPY configs/ configs/

# 安装依赖
RUN uv pip install --system --no-cache .

# 设置 Python 路径
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# 默认启动 FastAPI 服务
CMD ["uvicorn", "code_review.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

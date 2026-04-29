# ============================================================
# 阶段 1：构建前端
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build
COPY apps/frontend/package.json apps/frontend/package-lock.json* ./
RUN npm install
COPY apps/frontend/ ./
RUN npm run build

# ============================================================
# 阶段 2：构建后端 + 前端产物
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（仅需编译 asyncpg 等 C 扩展）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 优先复制依赖声明，安装所有依赖
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
RUN mkdir -p src/code_review && touch src/code_review/__init__.py && \
    uv pip install --system --no-cache . && \
    rm -rf src/code_review

# 复制后端源代码
COPY apps/backend/src/ src/

# 复制前端构建产物
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV STATIC_DIR=/app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "code_review.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

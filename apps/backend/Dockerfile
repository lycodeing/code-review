FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（编译 asyncpg 等 C 扩展）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 优先复制依赖声明，安装所有依赖
COPY pyproject.toml uv.lock ./
RUN mkdir -p src/code_review && touch src/code_review/__init__.py && \
    uv pip install --system --no-cache . && \
    rm -rf src/code_review

# 复制源代码
COPY src/ src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "code_review.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

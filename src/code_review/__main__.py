"""CLI 入口点。"""

import uvicorn


def main() -> None:
    """启动 FastAPI 服务。"""
    uvicorn.run(
        "code_review.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()

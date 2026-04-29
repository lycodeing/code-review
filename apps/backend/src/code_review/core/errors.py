"""可重试的临时错误定义。"""


class RetryableError(Exception):
    """可重试的临时错误（LLM 超时、网络错误、限流等）。"""

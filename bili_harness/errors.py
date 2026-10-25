"""错误分类：把接口返回的 code 变成「可重试 / 不该重试 / 需要人处理」三类。

为什么单独一层：我们踩过 -352 和 -799，两者的正确反应完全不同 ——
-352 是风控，继续打只会更糟；-799 是限流，退避后可能恢复。
分不清这两者，重试逻辑就永远写不对。
"""
from __future__ import annotations

RETRYABLE = {
    -799: "请求过于频繁（限流）",
    -509: "超出限制",
    -412: "请求被拦截",
}

NEEDS_HUMAN = {
    -352: "风控校验失败：需要人工介入，不要重试",
    -101: "账号未登录",
    -403: "访问权限不足",
}

FATAL = {
    -400: "请求错误",
    -404: "资源不存在",
}


class BiliError(RuntimeError):
    def __init__(self, code: int, message: str, endpoint: str = ""):
        self.code = code
        self.endpoint = endpoint
        super().__init__("code=%s %s%s" % (code, message, " @" + endpoint if endpoint else ""))

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE

    @property
    def needs_human(self) -> bool:
        return self.code in NEEDS_HUMAN


def classify(code: int, message: str, endpoint: str = "") -> BiliError:
    return BiliError(code, message, endpoint)

"""Typed 错误体系：所有可预期业务错误都继承 AppError，避免裸 raise。

全局异常处理器统一返回体：
  {"code": <http状态>, "message": <可读信息>, "data": null, "request_id": <rid>}
编程错误 → 记日志 + 落 system_logs + 返回通用 500（不向客户端暴露堆栈）。
"""


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_ERROR",
        status_code: int = 400,
        details=None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str = "资源", id_=None):
        msg = f"{resource}不存在" + (f": {id_}" if id_ else "")
        super().__init__(msg, "NOT_FOUND", 404)


class ValidationError(AppError):
    def __init__(self, message: str = "参数校验失败", details=None):
        super().__init__(message, "VALIDATION_ERROR", 422, details)


class AuthError(AppError):
    def __init__(self, message: str = "未认证或登录已过期，请重新登录"):
        super().__init__(message, "UNAUTHORIZED", 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权访问该资源"):
        super().__init__(message, "FORBIDDEN", 403)


class ConflictError(AppError):
    def __init__(self, message: str = "资源冲突，操作无法完成"):
        super().__init__(message, "CONFLICT", 409)

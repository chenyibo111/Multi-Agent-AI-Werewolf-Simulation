"""领域规则拒绝时使用的异常类型。"""


class DomainValidationError(ValueError):
    """表示领域对象自身不满足不可变契约。"""

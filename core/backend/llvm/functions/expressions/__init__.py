from .calls import CallExpressionMixin
from .memory import MemoryExpressionMixin
from .operators import OperatorExpressionMixin
from .values import ValueExpressionMixin


class ExpressionEmitterMixin(
    ValueExpressionMixin,
    MemoryExpressionMixin,
    OperatorExpressionMixin,
    CallExpressionMixin,
):
    """Compose expression emission responsibilities into one mixin."""

    pass


__all__ = ['ExpressionEmitterMixin']

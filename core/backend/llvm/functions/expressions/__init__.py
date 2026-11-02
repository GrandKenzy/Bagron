from .calls import CallExpressionMixin
from .conversions import ConversionExpressionMixin
from .memory import MemoryExpressionMixin
from .operators import OperatorExpressionMixin
from .values import ValueExpressionMixin


class ExpressionEmitterMixin(
    ConversionExpressionMixin,
    ValueExpressionMixin,
    MemoryExpressionMixin,
    OperatorExpressionMixin,
    CallExpressionMixin,
):
    """Compose expression emission responsibilities into one mixin."""

    pass


__all__ = ['ExpressionEmitterMixin']

from __future__ import annotations

from .base import FunctionEmitterBase
from .errors import FunctionEmissionError
from .expressions import ExpressionEmitterMixin
from .statements import StatementEmitterMixin


class FunctionEmitter(
    ExpressionEmitterMixin,
    StatementEmitterMixin,
    FunctionEmitterBase,
):
    """Compose LLVM function emission responsibilities into one public emitter."""

    pass


__all__ = ['FunctionEmissionError', 'FunctionEmitter']

from __future__ import annotations


class FunctionEmissionError(ValueError):
    """Raised when a supported function cannot be represented in LLVM yet."""


__all__ = ['FunctionEmissionError']

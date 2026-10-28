"""LLVM function emission package.

The package facade preserves the historical import path while the emitter
implementation is split into focused modules as the backend grows.
"""

from .emitter import FunctionEmissionError, FunctionEmitter

__all__ = ['FunctionEmissionError', 'FunctionEmitter']

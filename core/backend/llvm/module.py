from __future__ import annotations

from pathlib import Path

from llvmlite import binding as llvm
from llvmlite import ir

from core.backend.llvm.context import LLVMContextHandle
from core.backend.llvm.functions import FunctionEmitter
from core.backend.llvm.globals import GlobalEmitter
from core.backend.llvm.targets import TargetResolutionError


class BackendError(RuntimeError):
    pass


class LLVMBackend:
    """First-stage LLVM backend for validated global symbols."""

    def emit_module(self, storage, output: str | Path | None = None) -> Path:
        try:
            context = LLVMContextHandle.create(
                name=Path(storage.root).stem,
                target_request=storage.architecture,
            )
            GlobalEmitter(context.module).emit_storage(storage)
            FunctionEmitter(context.module).emit_storage(storage)
            module_text = str(context.module)
            verified = llvm.parse_assembly(module_text)
            verified.verify()
        except (TargetResolutionError, ValueError, RuntimeError) as error:
            raise BackendError(str(error)) from error

        output_path = Path(output) if output is not None else (
            Path(storage.root).parent / 'build' / f'{Path(storage.root).stem}.ll'
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(module_text, encoding='utf-8')
        return output_path


__all__ = ['BackendError', 'LLVMBackend']

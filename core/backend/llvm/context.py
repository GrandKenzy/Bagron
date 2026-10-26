from __future__ import annotations

from dataclasses import dataclass

from llvmlite import ir

from core.backend.llvm.targets import TargetHandle, resolve_target


@dataclass
class LLVMContextHandle:
    module: ir.Module
    target: TargetHandle

    @classmethod
    def create(cls, name: str, target_request: str | None = None):
        target = resolve_target(target_request)
        module = ir.Module(name=name)
        module.triple = target.triple
        module.data_layout = str(target.machine.target_data)
        return cls(module=module, target=target)

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from llvmlite import binding as llvm
from llvmlite import ir

from core.backend.llvm.context import LLVMContextHandle
from core.backend.llvm.functions import FunctionEmitter
from core.backend.llvm.globals import GlobalEmitter
from core.backend.llvm.targets import TargetResolutionError
from core.backend.llvm.types import LLVMTypeRegistry


class BackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class BuildArtifacts:
    ir: Path
    object_file: Path
    executable: Path
    prep_sources: tuple[Path, ...] = ()
    prep_objects: tuple[Path, ...] = ()


class LLVMBackend:
    """First-stage LLVM backend for validated global symbols."""

    def _emit_verified(self, storage):
        try:
            context = LLVMContextHandle.create(
                name=Path(storage.root).stem,
                target_request=storage.architecture,
            )
            type_registry = LLVMTypeRegistry(context.module, storage.types)
            GlobalEmitter(context.module, type_registry).emit_storage(storage)
            FunctionEmitter(context.module, type_registry).emit_storage(storage)
            module_text = str(context.module)
            verified = llvm.parse_assembly(module_text)
            verified.verify()
        except (TargetResolutionError, TypeError, ValueError, RuntimeError) as error:
            raise BackendError(str(error)) from error

        return context, module_text, verified

    def emit_module(self, storage, output: str | Path | None = None) -> Path:
        _, module_text, _ = self._emit_verified(storage)

        output_path = Path(output) if output is not None else (
            Path(storage.root).parent / 'build' / f'{Path(storage.root).stem}.ll'
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(module_text, encoding='utf-8')
        return output_path

    def build(self, storage, output_dir: str | Path | None = None) -> BuildArtifacts:
        context, module_text, verified = self._emit_verified(storage)
        root = Path(storage.root)
        build_dir = Path(output_dir) if output_dir is not None else root.parent / 'build'
        build_dir.mkdir(parents=True, exist_ok=True)

        stem = root.stem
        ir_path = build_dir / f'{stem}.ll'
        object_path = build_dir / f'{stem}.obj'
        executable_path = build_dir / f'{stem}.exe'

        ir_path.write_text(module_text, encoding='utf-8')
        try:
            object_path.write_bytes(context.target.machine.emit_object(verified))
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            raise BackendError(f'No se pudo generar el objeto LLVM: {error}') from error

        try:
            prep_objects = self._assemble_prep_sources(
                storage.prep_sources,
                context.target.triple,
            )
        except BackendError:
            raise

        storage.prep_objects = prep_objects
        self._link_object(
            [object_path, *prep_objects],
            executable_path,
            context.target.triple,
            storage.native_links,
        )
        return BuildArtifacts(
            ir=ir_path,
            object_file=object_path,
            executable=executable_path,
            prep_sources=tuple(storage.prep_sources),
            prep_objects=tuple(prep_objects),
        )

    @staticmethod
    def _assemble_prep_sources(
        sources: Sequence[Path],
        triple: str,
    ) -> list[Path]:
        if not sources:
            return []

        clang = shutil.which('clang')
        if clang is None:
            raise BackendError(
                'No se encontro clang para ensamblar funciones @assembler'
            )

        objects: list[Path] = []
        for source in sources:
            source = Path(source)
            object_path = source.with_suffix('.obj')
            command = [
                clang,
                f'--target={triple}',
                '-c',
                '-x',
                'assembler',
                str(source),
                '-o',
                str(object_path),
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise BackendError(
                    f'Clang excedio el limite al ensamblar {source}'
                ) from error
            except OSError as error:
                raise BackendError(
                    f'No se pudo ejecutar clang para ensamblar {source}: {error}'
                ) from error

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise BackendError(
                    f'Clang no pudo ensamblar {source} '
                    f'(codigo {result.returncode}): {detail}'
                )
            objects.append(object_path)
        return objects

    @staticmethod
    def _link_object(
        object_path: Path | Sequence[Path],
        executable_path: Path,
        triple: str,
        native_links: list[str] | tuple[str, ...] = (),
    ) -> None:
        clang = shutil.which('clang')
        if clang is None:
            raise BackendError(
                'No se encontro clang para enlazar el ejecutable. '
                'Instala LLVM y agrega clang al PATH.'
            )

        objects = [object_path] if isinstance(object_path, Path) else list(object_path)
        command = [
            clang,
            f'--target={triple}',
            '-fuse-ld=lld',
            *(str(path) for path in objects),
            *(f'-l{library}' for library in native_links),
            '-o',
            str(executable_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise BackendError(
                'El enlace con clang excedio el limite de 60 segundos'
            ) from error
        except OSError as error:
            raise BackendError(f'No se pudo ejecutar clang: {error}') from error

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BackendError(
                f'Clang no pudo enlazar el ejecutable (codigo {result.returncode}): '
                f'{detail}'
            )


__all__ = ['BackendError', 'BuildArtifacts', 'LLVMBackend']

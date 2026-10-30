from __future__ import annotations

import re
import shutil
import subprocess
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from llvmlite import binding as llvm
from llvmlite import ir

from core.backend.llvm.context import LLVMContextHandle
from core.backend.llvm.functions import FunctionEmitter
from core.backend.llvm.globals import GlobalEmitter
from core.backend.llvm.rodata import StringPool
from core.backend.llvm.targets import (
    TargetResolutionError,
    optimization_speed_level,
)
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
    raw_image: Path | None = None
    boot_image: Path | None = None


class LLVMBackend:
    """First-stage LLVM backend for validated global symbols."""

    @staticmethod
    def _has_large_stack_aggregate(function) -> bool:
        """Identify functions whose byte storage must remain opaque."""
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode != 'alloca':
                    continue
                dimensions = [
                    int(size)
                    for size in re.findall(r'\[(\d+) x', str(instruction))
                ]
                element_count = 1
                for dimension in dimensions:
                    element_count *= dimension
                if element_count > 1024:
                    return True
        return False

    @staticmethod
    def _optimise_module(module, target_machine, profile: object) -> None:
        """Run Bagron's selected whole-module LLVM optimisation pipeline."""
        speed_level = optimization_speed_level(profile)
        if speed_level == 0:
            return
        tuning = llvm.create_pipeline_tuning_options(speed_level=speed_level)
        # Bagron's explicit range guards produce several small control-flow
        # blocks per loop.  The default interprocedural O2 pipeline expands
        # imported library code through those guards pathologically.  Keep a
        # bounded, reusable sequence of local O2 transformations instead.
        pass_builder = llvm.create_pass_builder(target_machine, tuning)
        inline_passes = llvm.create_new_module_pass_manager()
        # ``inline`` is a Bagron contract in optimised profiles, not merely a
        # cost-model hint.  Only functions explicitly marked by Bagron carry
        # ``alwaysinline``; declarations and ASM entry points are untouched.
        inline_passes.add_always_inliner_pass()
        inline_passes.run(module, pass_builder)

        pass_manager = llvm.create_new_module_pass_manager()
        pass_manager.add_instruction_combine_pass()
        pass_manager.add_sccp_pass()
        pass_manager.add_simplify_cfg_pass()
        pass_manager.add_aggressive_dce_pass()
        if speed_level == 3:
            pass_manager.add_aggressive_instcombine_pass()
            pass_manager.add_simplify_cfg_pass()
        pass_manager.run(module, pass_builder)

        scalar_passes = llvm.create_new_function_pass_manager()
        scalar_passes.add_sroa_pass()
        scalar_passes.add_instruction_combine_pass()
        scalar_passes.add_sccp_pass()
        scalar_passes.add_simplify_cfg_pass()
        scalar_passes.add_aggressive_dce_pass()
        large_scalar_passes = llvm.create_new_function_pass_manager()
        large_scalar_passes.add_sroa_pass()

        # A large byte aggregate must stay addressable, but that does not
        # justify keeping every scalar local in memory. SROA's own aggregate
        # handling promotes scalar slots; avoid the later function passes for
        # these functions because they can repeatedly walk thousands of byte
        # stores introduced by an inline serializer.
        for function in module.functions:
            if function.is_declaration:
                continue
            if LLVMBackend._has_large_stack_aggregate(function):
                large_scalar_passes.run(function, pass_builder)
            else:
                scalar_passes.run(function, pass_builder)

        # The module pipeline ran before the large-function SROA pass. Do not
        # send its expanded byte stores through another whole-module walk.

    def _emit_verified(self, storage):
        try:
            context = LLVMContextHandle.create(
                name=Path(storage.root).stem,
                target_request=storage.architecture,
                system_request=storage.system,
                optimization_profile=storage.optimizers,
            )
            type_registry = LLVMTypeRegistry(
                context.module,
                storage.types,
                context.target.machine.target_data,
                pointer_size=getattr(storage, 'pointer_size', 8),
            )
            string_pool = StringPool(context.module)
            GlobalEmitter(
                context.module,
                type_registry,
                string_pool,
            ).emit_storage(storage)
            FunctionEmitter(
                context.module,
                type_registry,
                context.target.optimization_profile,
                string_pool,
            ).emit_storage(storage)
            raw_module_text = str(context.module)
            verified = llvm.parse_assembly(raw_module_text)
            verified.verify()
            if context.target.optimization_profile == 'dev':
                # Development mode keeps the historical textual IR useful for
                # diagnostics, while still validating the emitted module.
                module_text = raw_module_text
            else:
                self._optimise_module(
                    verified,
                    context.target.machine,
                    context.target.optimization_profile,
                )
                verified.verify()
                module_text = str(verified)
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
        baremetal = str(getattr(storage, 'system', '')).lower() == 'baremetal'
        boot = str(getattr(storage, 'boot', 'none')).lower()
        object_suffix = '.o' if baremetal else '.obj'
        object_path = build_dir / f'{stem}{object_suffix}'
        executable_path = build_dir / (
            f'{stem}.bin' if baremetal else f'{stem}.exe'
        )

        ir_path.write_text(module_text, encoding='utf-8')
        try:
            object_path.write_bytes(context.target.machine.emit_object(verified))
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            raise BackendError(f'No se pudo generar el objeto LLVM: {error}') from error

        try:
            prep_objects = self._assemble_prep_sources(
                storage.prep_sources,
                context.target.triple,
                getattr(storage, 'prep_metadata', None),
            )
        except BackendError:
            raise

        storage.prep_objects = prep_objects
        objects = [object_path, *prep_objects]
        raw_image = None
        boot_image = None
        if baremetal:
            if boot not in {'none', 'multiboot2'}:
                raise BackendError(
                    f'El perfil Boot {boot!r} esta reconocido, pero aun no '
                    'esta implementado por el backend bare-metal'
                )
            linker_script = build_dir / f'{stem}.ld'
            raw_image = build_dir / f'{stem}.bin'
            self._link_baremetal(
                objects,
                raw_image,
                context.target.triple,
                linker_script,
            )
            if boot == 'multiboot2':
                boot_image = self._build_baremetal_iso(raw_image, build_dir)
                executable_path = boot_image
        else:
            self._link_object(
                objects,
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
            raw_image=raw_image,
            boot_image=boot_image,
        )

    @staticmethod
    def _assemble_prep_sources(
        sources: Sequence[Path],
        triple: str,
        metadata: dict[Path, tuple[Path, str, str, int]] | None = None,
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
            object_suffix = '.obj' if 'windows' in triple.lower() else '.o'
            object_path = source.with_suffix(object_suffix)
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
                detail = LLVMBackend._format_assembler_diagnostic(
                    source,
                    detail,
                    metadata.get(source) if metadata else None,
                )
                raise BackendError(
                    f'Error de ensamblador en {source}: {detail}'
                )
            objects.append(object_path)
        return objects

    @staticmethod
    def _link_baremetal(
        object_paths: Sequence[Path],
        output_path: Path,
        triple: str,
        linker_script: Path,
    ) -> None:
        """Link ELF objects into a flat bare-metal binary."""
        ld = shutil.which('ld.lld')
        if ld is None:
            raise BackendError(
                'No se encontro ld.lld para enlazar el binario bare-metal'
            )

        architecture = triple.split('-', 1)[0].lower()
        emulations = {
            'i386': 'elf_i386',
            'i686': 'elf_i386',
            'x86': 'elf_i386',
            'x86_64': 'elf_x86_64',
            'amd64': 'elf_x86_64',
            'aarch64': 'aarch64elf',
            'arm': 'armelf',
            'armv6': 'armelf',
            'armv7': 'armelf',
            'riscv32': 'elf32lriscv',
            'riscv64': 'elf64lriscv',
        }
        emulation = emulations.get(architecture)
        if emulation is None:
            raise BackendError(
                f'No hay una emulacion ld.lld configurada para Arch {architecture!r}'
            )
        linker_script.write_text(
            '''ENTRY(_start)
SECTIONS
{
    . = 1M;

    .multiboot2 ALIGN(8) :
    {
        KEEP(*(.multiboot2))
    }

    .text ALIGN(16) :
    {
        *(.text*)
    }

    .rodata ALIGN(8) :
    {
        *(.rodata*)
    }

    .data ALIGN(8) :
    {
        *(.data*)
    }

    .bss ALIGN(16) :
    {
        *(COMMON)
        *(.bss*)
    }
}
''',
            encoding='utf-8',
        )

        command = [
            ld,
            '-m',
            emulation,
            '-T',
            str(linker_script),
            '--oformat=binary',
            '-o',
            str(output_path),
            *(str(path) for path in object_paths),
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
                'El enlace bare-metal con ld.lld excedio el limite de 60 segundos'
            ) from error
        except OSError as error:
            raise BackendError(
                f'No se pudo ejecutar ld.lld para el binario bare-metal: {error}'
            ) from error

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BackendError(
                f'ld.lld no pudo enlazar el binario bare-metal '
                f'(codigo {result.returncode}): {detail}'
            )

    @staticmethod
    def _find_baremetal_tools() -> tuple[str, str, str | None] | None:
        """Return native or WSL GRUB tooling available on this machine."""
        grub = shutil.which('grub-mkrescue')
        xorriso = shutil.which('xorriso')
        if grub and xorriso:
            return grub, xorriso, None

        wsl = shutil.which('wsl.exe') or shutil.which('wsl')
        if wsl is None:
            return None

        try:
            result = subprocess.run(
                [
                    wsl,
                    '-e',
                    'sh',
                    '-lc',
                    'command -v grub-mkrescue && command -v xorriso',
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        if result.returncode != 0:
            return None
        return wsl, wsl, wsl

    @staticmethod
    def _wsl_path(wsl: str, path: Path) -> str:
        try:
            result = subprocess.run(
                [wsl, '-e', 'wslpath', '-a', str(path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise BackendError(
                f'No se pudo convertir la ruta para WSL: {path}'
            ) from error
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BackendError(
                f'WSL no pudo convertir la ruta {path}: {detail}'
            )
        return result.stdout.strip()

    @staticmethod
    def _build_baremetal_iso(binary: Path, build_dir: Path) -> Path:
        tools = LLVMBackend._find_baremetal_tools()
        if tools is None:
            raise BackendError(
                'No se encontraron las herramientas para crear la ISO bare-metal: '
                'se requieren grub-mkrescue y xorriso. '
                'Instalalos en PATH o en WSL (Ubuntu: '
                'sudo apt install grub-pc-bin grub-common xorriso).'
            )

        data = binary.read_bytes()
        valid_header = False
        for offset in range(0, min(len(data), 32768), 8):
            if offset + 16 > len(data):
                break
            magic, architecture, length, checksum = struct.unpack_from(
                '<IIII', data, offset
            )
            if (
                magic == 0xE85250D6
                and architecture == 0
                and length >= 16
                and offset + length <= len(data)
                and (magic + architecture + length + checksum) & 0xFFFFFFFF == 0
            ):
                valid_header = True
                break
        if not valid_header:
            raise BackendError(
                f'El binario bare-metal {binary} no contiene una cabecera '
                'Multiboot2 alineada dentro de los primeros 32 KiB'
            )

        iso_root = build_dir / 'iso'
        boot_dir = iso_root / 'boot'
        grub_dir = boot_dir / 'grub'
        grub_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, boot_dir / binary.name)
        (grub_dir / 'grub.cfg').write_text(
            'set timeout=0\n'
            'set default=0\n'
            '\n'
            'menuentry "Bagron bare-metal" {\n'
            f'    multiboot2 /boot/{binary.name}\n'
            '    boot\n'
            '}\n',
            encoding='utf-8',
        )

        iso_path = build_dir / f'{binary.stem}.iso'
        tool, _, wsl = tools
        if wsl is None:
            command = [tool, '-o', str(iso_path), str(iso_root)]
        else:
            wsl_root = LLVMBackend._wsl_path(wsl, iso_root)
            wsl_iso = LLVMBackend._wsl_path(wsl, iso_path)
            command = [
                wsl,
                '-e',
                'grub-mkrescue',
                '-o',
                wsl_iso,
                wsl_root,
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
                'La creacion de la ISO bare-metal excedio el limite de 60 segundos'
            ) from error
        except OSError as error:
            raise BackendError(
                f'No se pudo ejecutar grub-mkrescue: {error}'
            ) from error

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BackendError(
                f'grub-mkrescue no pudo crear {iso_path} '
                f'(codigo {result.returncode}): {detail}'
            )
        return iso_path

    @staticmethod
    def _format_assembler_diagnostic(
        generated_source: Path,
        detail: str,
        metadata: tuple[Path, str, str, int] | None,
    ) -> str:
        """Map Clang's generated-file location back to the Bagron source."""
        if metadata is None:
            return f'Clang: {detail}'

        source, function_name, dialect, prep_line = metadata
        normalized = dialect.strip().lower()
        if normalized == 'intel':
            normalized = 'gas-intel'

        first_line, *rest = detail.splitlines()
        match = re.search(r':(?P<line>\d+):(?P<column>\d+):\s*', first_line)
        if match is None:
            return (
                f'{source}:{prep_line}: en la funcion @assembler '
                f'{function_name} (dialecto {normalized}): {detail}'
            )

        generated_line = int(match.group('line'))
        # Generated header: syntax, .text, .globl, symbol, optional status.
        try:
            generated_lines = generated_source.read_text(encoding='utf-8').splitlines()
        except OSError:
            generated_lines = []
        header_lines = 5 if (
            len(generated_lines) > 4
            and generated_lines[4].strip() in {'mov eax, 1', 'movl $1, %eax'}
        ) else 4
        source_line = prep_line + max(generated_line - header_lines, 0)
        message = first_line[match.end():].strip()
        formatted = (
            f'{source}:{source_line}: en la funcion @assembler {function_name} '
            f'(dialecto {normalized}, generado desde {generated_source}): '
            f'{message}'
        )
        if rest:
            formatted += '\n' + '\n'.join(rest)
        return formatted

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

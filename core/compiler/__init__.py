from dataclasses import dataclass
from pathlib import Path
from platform import machine, system

from core import globvars, storage
from core.compiler.control import CompilationError, CompilerState, _found_main
from core.compiler.prep import PrepBlock, PrepError, write_prep_files
from core.frontend import processor as bagron_processor


@dataclass(frozen=True)
class ModuleTarget:
    """Target clauses declared by one source module.

    ``None`` is intentional: an omitted dimension is agnostic and must not
    constrain the target selected by the project entry module.
    """

    system: str | None = None
    architecture: str | None = None
    boot: str | None = None


class Compiler(CompilerState):
    def __init__(self):
        super().__init__()
        self.storage = storage.Storage('main')
        self.function_lookup = storage.FunctionLookup(self.storage)
        self.project_root: Path | None = None
        self._loaded_module_paths: set[Path] = set()
        self._loading_module_paths: list[Path] = []
        self.import_requests = []
        self.module_exports: dict[Path, set[str]] = {}
        self.module_targets: dict[Path, ModuleTarget] = {}
        self.node_modules: dict[int, Path] = {}
        self.active_module_path: Path | None = None
        self.main_module_path: Path | None = None
        self.prep_blocks: list[PrepBlock] = []

    def module_for_node(self, node: object) -> Path | None:
        return self.node_modules.get(id(node), self.active_module_path)

    def activate_module(self, path: Path | None) -> None:
        """Set the module context used by flattened semantic lookups."""
        self.active_module_path = path.resolve() if path is not None else None
        self.storage.active_module_path = self.active_module_path

    @staticmethod
    def _node_token_value(node: object) -> object | None:
        token = getattr(node, 'token', None)
        return getattr(token, 'value', None)

    def _register_module_target(self, path: Path, nodes: list[object]) -> None:
        """Record target clauses before any flattened semantic pass runs."""
        values: dict[str, str] = {}
        seen: set[str] = set()
        for node in nodes:
            if getattr(node, 'name', None) != 'CLAUSE':
                continue
            children = getattr(node, 'nodes', ())
            if len(children) < 3:
                continue
            clause_name = self._node_token_value(children[1])
            clause_value = self._node_token_value(children[2])
            if clause_name not in ('System', 'Arch', 'Boot'):
                continue
            if clause_name in seen:
                self.error(
                    f'El modulo {path} declara la clausula {clause_name!r} mas de una vez'
                )
                continue
            seen.add(clause_name)
            values[clause_name] = str(clause_value)

        self.module_targets[path] = ModuleTarget(
            system=values.get('System'),
            architecture=values.get('Arch'),
            boot=values.get('Boot'),
        )

    @staticmethod
    def _normalize_target_system(value: str | None) -> str:
        normalized = str(value or 'auto').strip().lower()
        if normalized == 'auto':
            return system().lower()
        return normalized

    @staticmethod
    def _host_architecture() -> str:
        try:
            from core.backend.llvm.targets import resolve_target

            return resolve_target('auto').triple.split('-', 1)[0].lower()
        except (ImportError, RuntimeError, TypeError, ValueError):
            return str(machine() or 'unknown').strip().lower()

    @classmethod
    def _normalize_target_architecture(cls, value: str | None) -> str:
        normalized = str(value or 'auto').strip().lower()
        if normalized == 'auto':
            normalized = cls._host_architecture()
        else:
            normalized = normalized.split('-', 1)[0]

        aliases = {
            'amd': 'x86_64',
            'amd64': 'x86_64',
            'x86_64': 'x86_64',
            'x86': 'i386',
            'i386': 'i386',
            'i686': 'i386',
            'arm': 'aarch64',
            'arm64': 'aarch64',
            'aarch64': 'aarch64',
            'riscv32': 'riscv32',
            'riscv64': 'riscv64',
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _normalize_boot(value: str | None) -> str:
        return str(value or 'none').strip().lower()

    @staticmethod
    def _triple_environment(value: str | None) -> set[str]:
        """Return recognizable OS/environment components from an LLVM triple."""
        if not value or '-' not in value:
            return set()
        parts = [part.lower() for part in str(value).split('-')[1:]]
        known = {
            'linux', 'gnu', 'musl', 'windows', 'win32', 'mingw', 'msvc',
            'darwin', 'macos', 'ios', 'none', 'elf', 'uefi',
        }
        return {part for part in parts if part in known}

    @classmethod
    def _validate_target_configuration(
        cls,
        path: Path,
        system_name: str,
        architecture: str,
        boot: str,
        raw_architecture: str | None,
    ) -> None:
        """Reject target combinations that cannot describe one platform."""
        if system_name != 'baremetal' and boot != 'none':
            cls_error = (
                f'El modulo {path} declara Boot {boot!r}, pero System '
                f'{system_name!r} no admite un protocolo de arranque bare-metal'
            )
            raise ValueError(cls_error)

        if system_name == 'baremetal':
            if boot == 'multiboot2' and architecture not in {'i386', 'x86_64'}:
                raise ValueError(
                    f'El modulo {path} declara Boot "multiboot2" para Arch '
                    f'{architecture!r}; esta implementación solo soporta '
                    'x86/i386 y x86-64'
                )
            if boot == 'uefi' and architecture not in {'i386', 'x86_64', 'aarch64'}:
                raise ValueError(
                    f'El modulo {path} declara Boot "uefi" para Arch '
                    f'{architecture!r}; usa x86, amd o arm64'
                )
            if boot == 'opensbi' and not architecture.startswith('riscv'):
                raise ValueError(
                    f'El modulo {path} declara Boot "opensbi" para Arch '
                    f'{architecture!r}; OpenSBI requiere RISC-V'
                )

        environment = cls._triple_environment(raw_architecture)
        if system_name == 'baremetal' and environment & {
            'linux', 'gnu', 'musl', 'windows', 'win32', 'mingw', 'msvc',
            'darwin', 'macos', 'ios',
        }:
            raise ValueError(
                f'El modulo {path} combina System "baremetal" con un triple '
                f'con sistema operativo: {raw_architecture!r}'
            )
        if system_name == 'windows' and environment & {'linux', 'none', 'elf'}:
            raise ValueError(
                f'El modulo {path} combina System "windows" con el triple '
                f'{raw_architecture!r}'
            )
        if system_name == 'linux' and environment & {'windows', 'win32', 'msvc', 'none'}:
            raise ValueError(
                f'El modulo {path} combina System "linux" con el triple '
                f'{raw_architecture!r}'
            )

    def _validate_module_targets(self) -> None:
        """Validate every loaded module against the entry module target.

        The entry module selects the compilation target.  Imported modules may
        omit either dimension and are then agnostic for that dimension, but
        every omission is deliberately reported as a warning.
        """
        main_path = self.main_module_path
        if main_path is None:
            return

        main_target = self.module_targets.get(main_path, ModuleTarget())
        target_system = self._normalize_target_system(main_target.system)
        target_architecture = self._normalize_target_architecture(
            main_target.architecture
        )
        target_boot = self._normalize_boot(main_target.boot)

        if target_system == 'baremetal' and main_target.boot is None:
            self.error(
                'El target baremetal requiere una clausula Boot explicita; '
                'usa "none", "multiboot2", "uefi", "opensbi", "dtb" o "custom"'
            )
        try:
            self._validate_target_configuration(
                main_path,
                target_system,
                target_architecture,
                target_boot,
                main_target.architecture,
            )
        except ValueError as error:
            self.error(str(error))

        for path, module_target in self.module_targets.items():
            missing: list[str] = []
            if module_target.system is None:
                missing.append('System')
            if module_target.architecture is None:
                missing.append('Arch')
            if target_boot != 'none' and module_target.boot is None:
                missing.append('Boot')
            if missing:
                self.warning(
                    f'El modulo {path} no define {" ni ".join(missing)}; '
                    'se considera agnostico para esas dimensiones del target'
                )

            if (
                module_target.system is not None
                and self._normalize_target_system(module_target.system)
                != target_system
            ):
                self.error(
                    f'El modulo {path} declara System '
                    f'{module_target.system!r}, incompatible con el target del proyecto '
                    f'{target_system!r}'
                )

            if (
                module_target.architecture is not None
                and self._normalize_target_architecture(module_target.architecture)
                != target_architecture
            ):
                self.error(
                    f'El modulo {path} declara Arch '
                    f'{module_target.architecture!r}, incompatible con el target del proyecto '
                    f'{target_architecture!r}'
                )

            if (
                module_target.boot is not None
                and self._normalize_boot(module_target.boot) != target_boot
            ):
                self.error(
                    f'El modulo {path} declara Boot '
                    f'{module_target.boot!r}, incompatible con el target del '
                    f'proyecto {target_boot!r}'
                )

            if module_target.system is not None or module_target.architecture is not None:
                # An omitted dimension is agnostic, so validate it using the
                # entry target instead of the host target.  This matters for
                # modules that declare an ELF triple but omit System.
                module_system = (
                    target_system
                    if module_target.system is None
                    else self._normalize_target_system(module_target.system)
                )
                module_architecture = (
                    target_architecture
                    if module_target.architecture is None
                    else self._normalize_target_architecture(
                        module_target.architecture
                    )
                )
                module_boot = (
                    target_boot
                    if module_target.boot is None
                    else self._normalize_boot(module_target.boot)
                )
                try:
                    self._validate_target_configuration(
                        path,
                        module_system,
                        module_architecture,
                        module_boot,
                        module_target.architecture or main_target.architecture,
                    )
                except ValueError as error:
                    self.error(str(error))

    def _load_module_tree(self, path: Path):
        path = path.resolve()
        if path in self._loading_module_paths:
            cycle = ' -> '.join(
                str(item) for item in (*self._loading_module_paths, path)
            )
            self.error(f'Ciclo de importacion detectado: {cycle}')
            return []
        if path in self._loaded_module_paths:
            return []
        if path.suffix != '.bg':
            self.error(f'El modulo importado no es un archivo .bg: {path}')
            return []
        if not path.is_file():
            self.error(f'El modulo Bagron no existe: {path}')
            return []

        from core.frontend.tools import imports

        self._loading_module_paths.append(path)
        try:
            nodes = self.process_source(path)
            for node in nodes:
                self.node_modules[id(node)] = path
            self._register_module_target(path, nodes)
            ordered = []
            for node in nodes:
                if node.name != 'IMPORT':
                    continue
                name = imports.module_name(node)
                if name is None:
                    self.error(
                        f'La declaracion import no contiene un modulo valido: '
                        f'{path}'
                    )
                    continue
                imported_path = imports.resolve_module_path(self, name, path)
                if imported_path is not None:
                    request = imports.parse_request(
                        node,
                        target=imported_path,
                        source=path,
                    )
                    if request is not None:
                        self.import_requests.append(request)
                    ordered.extend(self._load_module_tree(imported_path))

            own_nodes = [node for node in nodes if node.name != 'IMPORT']
            self.module_exports[path] = imports.public_definition_names(own_nodes)
            self._loaded_module_paths.add(path)
            self.storage.loaded_modules.append(str(path))
            return ordered + own_nodes
        finally:
            self._loading_module_paths.pop()

    def compile(self, path: Path | str, executable: bool = True):
        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            self.error(f'El source {path} no existe. Por favor, elija una ruta válida')
            self.exit()

        if path.is_dir():
            globvars.BASEDIR = path
            r = _found_main(path)
            if not r:
                self.error(f'No se encontró main.bg en {path}')
                self.exit()
            else:
                path = r

        path = path.resolve()
        globvars.BASEDIR = path.parent
        self.project_root = path.parent
        self.main_module_path = path
        self._loaded_module_paths.clear()
        self._loading_module_paths.clear()
        self.import_requests.clear()
        self.module_exports.clear()
        self.module_targets.clear()
        self.node_modules.clear()
        self.semantic_errors.clear()
        self.warnings.clear()
        self.activate_module(None)
        self.prep_blocks.clear()
        self.storage.prep_sources.clear()
        self.storage.prep_objects.clear()
        self.storage.prep_metadata.clear()
        self.storage.root = str(path)

        AST = self._load_module_tree(path)

        self._validate_module_targets()
        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        bagron_processor.process(self, AST)

        for block in self.prep_blocks:
            if block.is_module:
                continue
            if block.function_name not in self.storage.functions:
                self.error(
                    f'El bloque ASM de {block.source}:{block.line} no pertenece '
                    f'a una funcion global emitible: {block.function_name}'
                )

        main = self.storage.functions.get('main')
        if main is None:
            self.error('No se encontro la funcion global main')
        else:
            if main.signature.parameters:
                self.error('La funcion global main no puede recibir parametros')
            if (
                main.signature.return_type.name != 'int32'
                or main.signature.return_type.pointer_level
                or main.signature.return_type.array_depth
            ):
                self.error('La funcion global main debe retornar int32')
            if 'main' in self.storage.namespace:
                self.error('El nombre main no puede ser variable y funcion global a la vez')

        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        if self.prep_blocks:
            from core.backend.llvm.targets import TargetResolutionError, resolve_target

            try:
                target = resolve_target(
                    self.storage.architecture,
                    self.storage.system,
                )
                self.storage.prep_sources = write_prep_files(
                    self.prep_blocks,
                    self.project_root or path.parent,
                    functions=self.storage.functions,
                    target_triple=target.triple,
                )
                self.storage.prep_metadata = {
                    generated: (
                        block.source,
                        block.function_name or '<module>',
                        block.dialect,
                        block.line,
                    )
                    for generated, block in zip(
                        self.storage.prep_sources,
                        self.prep_blocks,
                    )
                }
            except (PrepError, TargetResolutionError) as error:
                raise CompilationError(str(error)) from error
        else:
            write_prep_files([], self.project_root or path.parent)

        from core.backend.llvm import LLVMBackend
        from core.backend.llvm.module import BackendError

        try:
            backend = LLVMBackend()
            if executable:
                return backend.build(self.storage)
            return backend.emit_module(self.storage)
        except BackendError as error:
            raise CompilationError(str(error)) from error

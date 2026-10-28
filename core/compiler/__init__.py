from pathlib import Path

from core import globvars, storage
from core.compiler.control import CompilationError, CompilerState, _found_main
from core.compiler.prep import PrepBlock, PrepError, write_prep_files
from core.frontend import processor as bagron_processor


class Compiler(CompilerState):
    def __init__(self):
        super().__init__()
        self.storage = storage.Storage('main')
        self.project_root: Path | None = None
        self._loaded_module_paths: set[Path] = set()
        self._loading_module_paths: list[Path] = []
        self.import_requests = []
        self.module_exports: dict[Path, set[str]] = {}
        self.prep_blocks: list[PrepBlock] = []

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
                    request = imports.parse_request(node, target=imported_path)
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
        self._loaded_module_paths.clear()
        self._loading_module_paths.clear()
        self.import_requests.clear()
        self.module_exports.clear()
        self.prep_blocks.clear()
        self.storage.prep_sources.clear()
        self.storage.prep_objects.clear()
        self.storage.root = str(path)

        AST = self._load_module_tree(path)

        bagron_processor.process(self, AST)

        for block in self.prep_blocks:
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
                main.signature.return_type.name != 'int'
                or main.signature.return_type.pointer_level
                or main.signature.return_type.array_depth
            ):
                self.error('La funcion global main debe retornar int')
            if 'main' in self.storage.namespace:
                self.error('El nombre main no puede ser variable y funcion global a la vez')

        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        if self.prep_blocks:
            from core.backend.llvm.targets import TargetResolutionError, resolve_target

            try:
                target = resolve_target(self.storage.architecture)
                self.storage.prep_sources = write_prep_files(
                    self.prep_blocks,
                    self.project_root or path.parent,
                    functions=self.storage.functions,
                    target_triple=target.triple,
                )
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

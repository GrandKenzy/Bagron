from pathlib import Path

from core import globvars, storage
from core.compiler.control import CompilationError, CompilerState, _found_main
from core.frontend import processor as bagron_processor


class Compiler(CompilerState):
    def __init__(self):
        super().__init__()
        self.storage = storage.Storage('main')

    def compile(self, path: Path | str):
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

        AST = self.process_source(path)

        self.storage.root = str(path)

        bagron_processor.process(self, AST)

        main = self.storage.functions.get('main')
        if main is None:
            self.error('No se encontro la funcion global main')
        else:
            if main.signature.parameters:
                self.error('La funcion global main no puede recibir parametros')
            if main.signature.return_type.name != 'bool':
                self.error('La funcion global main debe retornar bool')
            if 'main' in self.storage.namespace:
                self.error('El nombre main no puede ser variable y funcion global a la vez')

        if self.semantic_errors:
            raise CompilationError('\n'.join(self.semantic_errors))

        from core.backend.llvm import LLVMBackend
        from core.backend.llvm.module import BackendError

        try:
            return LLVMBackend().emit_module(self.storage)
        except BackendError as error:
            raise CompilationError(str(error)) from error

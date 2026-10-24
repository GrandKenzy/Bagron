from pathlib import Path

from core import globvars, storage
from core.compiler.control import CompilerState, _found_main
from core.frontend.C import processor as c_processor
from core.frontend.EASYC import processor as ec_processor


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
                self.error(f'No se encontró main.ec ni main.c en {path}')
                self.exit()
            else:
                path = r

        AST, LANG = self.process_source(path)

        self.storage.root = str(path)

        if LANG == 0: # procesar entrada C
            c_processor.process(self, AST)
        else: # procesar entrada EC.
            ec_processor.process(self, AST)
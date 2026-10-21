from pathlib import Path

from core import globvars
from core.compiler.control import CompilerState, _found_main


class Compiler(CompilerState):
    def __init__(self):
        pass
    
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
                self.error(f'No se encontró main.egl ni main.c en {path}')
            else: path = r
        
        self.process_source(path)
        
        
    
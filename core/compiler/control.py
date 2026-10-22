import sys
from pathlib import Path

from core.frontend import EASYC, C
from tools.diagnostic import Diagnostics


class CompilerState(Diagnostics):
    def __init__(self):
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)
    
    def exit(self): # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(0)
        
    def process_source(self, path: Path):
        ext = path.suffix

        content = _open_file(self, path)
        
        
        ext = ext.strip('.')
        if ext == 'ec':
            EASYC.EASY_C_SESSION.load()
            TKNS = EASYC.EASY_C_SESSION.tokenize(content, path.name)
            return EASYC.EASY_C_SESSION.parse(TKNS, path.name)

        elif ext == 'c':
            C.C_SESSION.load()
            TKNS = C.C_SESSION.tokenize(content, path.name)
            return C.C_SESSION.parse(TKNS, path.name)

        else:
            self.error(f'La extensión {ext} no está soportada.')
            self.exit()
        

def _found_main(source: Path):
    for p in source.iterdir():
        if p.is_dir():
            continue
        if p.name in ('main.ec', 'main.c'):
            return p
    return None
        
def _open_file(cdiag: CompilerState, source: str | Path):
    if isinstance(source, str): source = Path(source)
        
    if not source.exists():
        cdiag.error(f'El archivo especificado no existe: {source}')
        cdiag.exit()
    
    try:
        content = source.read_text(encoding='utf-8')
    except PermissionError as e:
        cdiag.fatal(f'No se pudo abrir {source}. Permiso denegado: {e}')
        cdiag.exit()
        
    return content.splitlines(keepends=True)    
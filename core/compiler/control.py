import sys
from pathlib import Path

from core.frontend import EASYC
from tools.diagnostic import Diagnostics


class CompilerState(Diagnostics):
    def __init__(self):
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)
    
    def exit(self): # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(0)
        
    def process_source(self, path: Path):
        ext = path.name.split('.')[1]

        content = _open_file(self, path)
        
        
        if ext == 'ec':
            EASYC.EASY_C_SESSION.load()
            TKNS = EASYC.EASY_C_SESSION.tokenize(content, path.name)
            return EASYC.EASY_C_SESSION.parse(TKNS, path.name)

        
        

def _found_main(source: Path):
    for p in source.iterdir():
        if p.is_dir():
            continue
        if p.name in ('main.egl', 'app.egl'):
            return p
    return None
        
def _open_file(cdiag: CompilerState, source: str | Path):
    if isinstance(source, str): source = Path(source)
        
    if not source.exists():
        cdiag.error(f'El archivo especificado no existe: {source}')
        cdiag.exit()
    
    content = source.read_text(encoding='utf-8')
    return content.splitlines(keepends=True)    
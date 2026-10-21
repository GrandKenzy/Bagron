import sys
from pathlib import Path

from tools.diagnostic import Diagnostics

from gram import lexer

class CompilerDiagnostic(Diagnostics):
    def __init__(self):
        super().__init__('Compiler', 'Compiler', 'Diagnostics for compiler', True, True, True)
    
    def exit(self): # NOTE: Función temporal en lo que armamos los errores
        print(self.last_note())
        sys.exit(0)
        
    def compile_source(self, path: Path, storage: Storage):
        content = _open_file(self, path)
        lx = lexer.Lexer(content, logfile=path.name)
        tokens = lx.process()
        

def _found_main(source: Path):
    for p in source.iterdir():
        if p.is_dir():
            continue
        if p.name in ('main.egl', 'app.egl'):
            return p
    return None
        
def _open_file(cdiag: CompilerDiagnostic, source: str | Path):
    if isinstance(source, str): source = Path(source)
        
    if not source.exists():
        cdiag.error(f'El archivo especificado no existe: {source}')
        cdiag.exit()
    
    content = source.read_text(encoding='utf-8')
    return content.splitlines(keepends=True)    
from pathlib import Path

from core.backend.ec.visitors import (
    visit_class,
    visit_enum,
    visit_function,
    visit_struct,
    visit_type_alias,
    visit_var,
)
from core.processor.objects import (
    ClassDecl,
    EnumDecl,
    Function,
    StructDecl,
    TypeAlias,
    Variable,
)
from core.processor.storage import Storage

"""
INFO: ¿Por qué usar la variable generate_heading?

El código generado en program.c no es para uso en C por el el excesivo cambio de nombres (mangling).

Sin embargo, no podemos quitarle la capacidad al usuario. Además de que podría servir para otras cosas esenciales.

Archivos sin importaciones funcionarán perfectamente bien sin el mangling.

Sin embargo, hay que caer en cuenta que los nombres de los simbolos no son legibles, se usarán numeros (hashes u otras medidas) para evitar de forma más certera la colisión de nombres.

"""

class Files:
    def __init__(self, root: str | Path, genh: bool = False):
        self.root = Path(root)
        self.header = self.root / 'program.h'
        self.program = self.root / 'program.c'
        self.code: list[str] = []
        self.headings: list[str] = []
        self.genh: bool = genh

    def add(self, code: str, heading: str | None):
        if code:
            self.code.append(code)
        if self.genh and heading:
            self.headings.append(heading)

    def write(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if self.code:
            self.program.write_text("\n\n".join(self.code) + "\n", encoding='utf-8')
        if self.genh and self.headings:
            self.header.write_text("\n\n".join(self.headings) + "\n", encoding='utf-8')


def _emit_storage(f: Files, storage: Storage):
    if not storage.bpoint:
        return

    mod_name = storage.root.stem
    banner = f"/* --- MODULE: {mod_name} ({storage.mangling_prefix}) --- */" if not storage.is_main else "/* --- MAIN ENTRYPOINT --- */"
    f.add(f"\n{banner}", None)

    for pointer in storage.bpoint:
        if isinstance(pointer, Variable):
            f.add(*visit_var(pointer, storage=storage))
        elif isinstance(pointer, Function):
            f.add(*visit_function(pointer, storage=storage))
        elif isinstance(pointer, EnumDecl):
            f.add(*visit_enum(pointer))
        elif isinstance(pointer, StructDecl):
            f.add(*visit_struct(pointer, storage=storage))
        elif isinstance(pointer, TypeAlias):
            f.add(*visit_type_alias(pointer))
        elif isinstance(pointer, ClassDecl):
            f.add(*visit_class(pointer))
        
        
        else:
            print('Falta por procesar', pointer.name)


def compile(storage: Storage, generate_heading: bool = False) -> Files:
    from core.compiler import Environment

    build_dir = (Environment.basedir or storage.root.parent) / 'build'
    f = Files(build_dir, generate_heading)

    # 0. Inyectar encabezados estándar esenciales para C y helpers de runtime C


    # 1. Procesar módulos en orden de importación antes que el código de main
    for mod_storage in storage.ordered_modules:
        _emit_storage(f, mod_storage)

    # 2. Procesar el código principal (main)
    _emit_storage(f, storage)

    f.write()
    
    print('C generating in', f.program)
    return f
from pathlib import Path
from typing import Any

from core.processor.objects.array import Array
from core.processor.objects.enum_decl import EnumDecl
from core.processor.objects.function import Function
from core.processor.objects.struct_decl import StructDecl, StructField
from core.processor.objects.type_decl import TypeAlias
from core.processor.objects.variable import Variable



class Storage:
    def __init__(self, root: Path, main_storage: 'Storage | None' = None):
        self.main_storage: 'Storage | None' = main_storage
        self.is_main: bool = main_storage is None
        self.ordered_modules: list['Storage'] = []
        self.loaded_modules: dict[Path, 'Storage'] = {}
        self.in_progress: set[Path] = set()
        self.imports: dict[str, str | None] = {}
        self.includes: dict[str, str | None] = {}
        self.declarations: dict[str, str | None] = {}
        self.modules: dict[str, 'Storage'] = {}
        self.externs: dict[str, dict] = {}
        self.variables: dict[str, Variable] = {}
        self.enums: dict[str, EnumDecl] = {}
        self.structs: dict[str, StructDecl] = {}
        self.classes: dict[str, Any] = {}
        self.functions: dict[str, Function] = {}
        self.types: dict[str, TypeAlias] = {}
        self.statements: list[Any] = []
        self.warnings: list[str] = []
        self.root = root

        # Hashes para mangling reproducible
        # 1. folder_hash: hash del nombre de la carpeta base (o 'main' si se ejecutó archivo directo)
        from core.compiler import Environment
        import hashlib

        if Environment.basedir is not None:
            folder_name = Environment.basedir.name
            self.folder_hash = hashlib.sha256(folder_name.encode('utf-8')).hexdigest()[:8]
        else:
            self.folder_hash = 'main'

        # 2. module_hash: hash del nombre del módulo (stem del archivo)
        mod_stem = root.stem
        self.module_hash = hashlib.sha256(mod_stem.encode('utf-8')).hexdigest()[:8]

        # Prefijo base precalculado: folder_hash + '_' + module_hash + '_module'
        self.mangling_prefix = f"{self.folder_hash}_{self.module_hash}_module"

        # clausulas
        self.arch = 'auto'
        self.system = 'auto'
        self.privacy: str = 'public'
        self.stacklimit = -1  # automático
        self.bpoint = []

    @property
    def type_aliases(self) -> dict[str, TypeAlias]:
        return self.types

    def collition_name(self, name: str, raise_error: bool = True) -> bool:
        from core.initiator.reserve_funnames import MagicFuncsManager

        if MagicFuncsManager.exists(name):
            if raise_error:
                raise RuntimeError(
                    f"Colisión: '{name}' es una función intrínseca reservada y no puede ser reemplazada."
                )
            return True

        collided = (
            name in self.variables
            or name in self.enums
            or name in self.structs
            or name in self.classes
            or name in self.functions
            or name in self.types
            or name in self.imports
            or name in self.includes
            or name in self.declarations
            or name in self.modules
        )
        if collided and raise_error:
            raise RuntimeError(f"Colisión: el símbolo '{name}' ya existe en el ámbito actual.")
        return collided

    def resolve(self, name: str) -> Any | None:
        """Busca un símbolo en el almacenamiento global."""
        if name in self.variables:
            return self.variables[name]
        if name in self.functions:
            return self.functions[name]
        if name in self.structs:
            return self.structs[name]
        if name in self.classes:
            return self.classes[name]
        if name in self.enums:
            return self.enums[name]
        if name in self.types:
            return self.types[name]
        if name in self.declarations:
            target = self.declarations[name]
            if target and '|' in target:
                mod_name, sym = target.split('|', 1)
                if mod_name in self.modules:
                    return self.modules[mod_name].resolve(sym)
            return target
        if name in self.imports:
            return self.imports[name]
        if name in self.includes:
            return self.includes[name]
        if name in self.modules:
            return self.modules[name]
        return None

    def resolve_type(self, type_name: str) -> str:
        """Resuelve un tipo a su tipo base si es un alias registrado o clase."""
        if type_name in self.classes:
            return type_name
        visited = set()
        current = type_name
        while current in self.types and current not in visited:
            visited.add(current)
            current = self.types[current].target_type
        return current

    def find_struct(self, name: str, visited: set[int] | None = None) -> StructDecl | None:
        """Busca un struct, mold o flags localmente o a través de módulos importados."""
        if visited is None:
            visited = set()
        if id(self) in visited:
            return None
        visited.add(id(self))

        if '.' in name:
            mod_alias, sym = name.split('.', 1)
            if mod_alias in self.modules:
                return self.modules[mod_alias].find_struct(sym, visited)
        if name in self.structs:
            return self.structs[name]
        if name in self.declarations:
            target = self.declarations[name]
            if target and '|' in target:
                mod_name, sym = target.split('|', 1)
                if mod_name in self.modules:
                    return self.modules[mod_name].find_struct(sym, visited)
        for mod in self.modules.values():
            if name in mod.structs:
                return mod.structs[name]
            found = mod.find_struct(name, visited)
            if found is not None:
                return found
        if self.main_storage is not None and self.main_storage is not self:
            return self.main_storage.find_struct(name, visited)
        return None

    def find_enum(self, name: str, visited: set[int] | None = None) -> EnumDecl | None:
        """Busca un enum localmente o a través de módulos importados."""
        if visited is None:
            visited = set()
        if id(self) in visited:
            return None
        visited.add(id(self))

        if '.' in name:
            mod_alias, sym = name.split('.', 1)
            if mod_alias in self.modules:
                return self.modules[mod_alias].find_enum(sym, visited)
        if name in self.enums:
            return self.enums[name]
        if name in self.declarations:
            target = self.declarations[name]
            if target and '|' in target:
                mod_name, sym = target.split('|', 1)
                if mod_name in self.modules:
                    return self.modules[mod_name].find_enum(sym, visited)
        for mod in self.modules.values():
            if name in mod.enums:
                return mod.enums[name]
            found = mod.find_enum(name, visited)
            if found is not None:
                return found
        if self.main_storage is not None and self.main_storage is not self:
            return self.main_storage.find_enum(name, visited)
        return None

    def find_function(self, name: str, visited: set[int] | None = None) -> Function | None:
        """Busca una función localmente o a través de módulos importados."""
        if visited is None:
            visited = set()
        if id(self) in visited:
            return None
        visited.add(id(self))

        if '.' in name:
            mod_alias, sym = name.split('.', 1)
            if mod_alias in self.modules:
                return self.modules[mod_alias].find_function(sym, visited)
        if name in self.functions:
            return self.functions[name]
        if name in self.declarations:
            target = self.declarations[name]
            if target and '|' in target:
                mod_name, sym = target.split('|', 1)
                if mod_name in self.modules:
                    return self.modules[mod_name].find_function(sym, visited)
        for mod in self.modules.values():
            if name in mod.functions:
                return mod.functions[name]
            found = mod.find_function(name, visited)
            if found is not None:
                return found
        if self.main_storage is not None and self.main_storage is not self:
            return self.main_storage.find_function(name, visited)
        return None

    def add_import(self, name: str, alias: str | None):
        if not alias:
            self.imports[name] = None
        else:
            self.imports[alias] = name

    def add_include(self, name: str, alias: str | None):
        if not alias:
            self.includes[name] = None
        else:
            self.includes[alias] = name

    def add_declaration(self, name: str, alias: str | None):
        if not alias:
            self.declarations[name] = None
        else:
            self.declarations[alias] = name

    def add_module(self, name: str, storage: 'Storage'):
        self.modules[name] = storage
        target_main = self.main_storage or self
        if storage not in target_main.ordered_modules:
            target_main.ordered_modules.append(storage)

    def add_extern(self, name: str, symbols: dict, metadata: dict):
        self.externs[name] = {
            'symbols': symbols,
            'metadata': metadata,
        }

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_variable(
        self,
        name: str,
        var_type: str,
        value: Any = None,
        privacy: str = 'public',
        fixed_size: int | None = None,
        pointer_base_type: str | None = None,
        is_cptr: bool = False,
        is_ptr: bool = False,
        array: Array | None = None,
    ) -> Variable:
        computed_is_cptr = is_cptr or var_type == 'cptr'
        computed_is_ptr = is_ptr or var_type == 'ptr'
        actual_type = 'void' if var_type in ('cptr', 'ptr') else var_type

        if array is None and (fixed_size is not None or var_type.startswith('array[')):
            elem_type = var_type[6:-1].split(',')[0].strip() if var_type.startswith('array[') else var_type
            if elem_type in ('cptr', 'ptr'):
                elem_type = 'void'
            array = Array(
                element_type=elem_type,
                size=fixed_size,
                is_cptr=computed_is_cptr,
                is_ptr=computed_is_ptr,
                pointer_base_type=pointer_base_type or (elem_type if (computed_is_cptr or computed_is_ptr) else None),
            )

        # Contrato de mangling: _ec_{folder_hash}_{module_hash}_module_{name}
        c_mangled_name = f"_ec_{self.mangling_prefix}_{name}"

        var_obj = Variable(
            name=name,
            value=value,
            type=actual_type,
            privacy=privacy,  # type: ignore
            is_constant=name.isupper() or computed_is_cptr,
            is_cptr=computed_is_cptr,
            is_ptr=computed_is_ptr,
            array=array,
            c_name=c_mangled_name,
        )
        if fixed_size is not None:
            var_obj.fixed_size = fixed_size
        var_obj.pointer_base_type = pointer_base_type or (actual_type if (computed_is_cptr or computed_is_ptr) else None)
        self.variables[name] = var_obj

        self.bpoint.append(var_obj)
        return var_obj



    def add_enum(self, name: str, items: list[tuple[str, Any]], privacy: str = 'public') -> EnumDecl:
        c_mangled_name = f"_ec_{self.mangling_prefix}_{name}"
        enum_obj = EnumDecl(
            name=name,
            items=items,
            privacy=privacy,
            c_name=c_mangled_name,
        )
        self.enums[name] = enum_obj
        self.bpoint.append(enum_obj)
        return enum_obj

    def add_struct(
        self,
        name: str,
        fields: list[StructField],
        privacy: str = 'public',
        is_packed: bool = False,
        is_volatile: bool = False,
        align: int | str | None = None,
        kind: str = 'struct',
    ) -> StructDecl:
        c_mangled_name = f"_ec_{self.mangling_prefix}_{name}"
        struct_obj = StructDecl(
            name=name,
            fields=fields,
            privacy=privacy,
            is_packed=is_packed,
            is_volatile=is_volatile,
            align=align,
            kind=kind, # type: ignore
            in_scope=self,
            c_name=c_mangled_name,
        )
        self.structs[name] = struct_obj
        self.bpoint.append(struct_obj)
        return struct_obj

    def add_function(
        self,
        name: str,
        return_type: str,
        parameters: list[Any] | Any = None,
        body: Any = None,
        privacy: str = 'public',
        is_inline: bool = False,
        decorators: list[Any] | None = None,
    ) -> Function:
        if self.is_main and name == 'main':
            c_mangled_name = 'main'
        else:
            c_mangled_name = f"_ec_{self.mangling_prefix}_{name}"

        func_obj = Function(
            name=name,
            return_type=return_type,
            parameters=parameters,
            body=body,
            privacy=privacy,
            is_inline=is_inline,
            decorators=decorators,
            c_name=c_mangled_name,
        )
        self.functions[name] = func_obj
        self.bpoint.append(func_obj)
        return func_obj

    def add_type_alias(
        self,
        name: str,
        target_type: str,
        privacy: str = 'public',
    ) -> TypeAlias:
        alias_obj = TypeAlias(
            name=name,
            target_type=target_type,
            privacy=privacy,
        )
        self.types[name] = alias_obj
        self.bpoint.append(alias_obj)
        return alias_obj

    @property
    def molds(self) -> dict[str, StructDecl]:
        return {k: v for k, v in self.structs.items() if v.kind == 'mold'}

    @property
    def flags(self) -> dict[str, StructDecl]:
        return {k: v for k, v in self.structs.items() if v.kind == 'flags'}

    def add_class(self, name: str, class_obj: Any) -> Any:
        self.classes[name] = class_obj
        self.bpoint.append(class_obj)
        return class_obj
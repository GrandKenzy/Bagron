from pathlib import Path
from typing import Any

from tools import diagnostic

from core.frontend.objects import (
    AggregateSymbol,
    EnumSymbol,
    FunctionSymbol,
    Variable,
)

from platform import system, architecture

SemanticObject = Variable


class FunctionLookup:
    """Context-aware view of the flattened function namespace."""

    def __init__(self, storage: 'Storage'):
        self.storage = storage

    def resolve_for(
        self,
        name: str,
        current_function: object | None = None,
    ) -> FunctionSymbol | None:
        function = self.storage.functions.get(name)
        if function is None or getattr(function, 'privacy', 'public') != 'private':
            return function
        origin = getattr(function, 'module_path', None)
        active = getattr(current_function, 'module_path', None)
        if active is None:
            active = self.storage.active_module_path
        return function if origin is None or origin == active else None

    def get(self, name: str, default=None):
        function = self.resolve_for(name)
        return function if function is not None else default


class Storage(diagnostic.Diagnostics):
    Main: 'Storage | None' = None
    
    def __init__(
        self,
        root: str,
        parent: 'Storage | None' = None,
        scope_name: str = 'module',
        function_scope: bool = False,
    ):
        self.main: bool = False
        self.root = root        
        self.parent = parent
        self.scope_name = scope_name
        self.is_function_scope = function_scope
        self._function_root = self if function_scope else (
            parent._function_root if parent is not None else None
        )
        # Names in this shared set are the only module data bindings visible
        # from a function/method lexical scope. Child block scopes reuse the
        # same set, so ``global`` is function-wide rather than block-local.
        self.global_names: set[str] = (
            set()
            if function_scope
            else (
                parent.global_names
                if parent is not None
                else set()
            )
        )
        # The compiler changes this value while validating one module.  All
        # lexical child scopes consult the module root so private declarations
        # from another imported module cannot leak through the flattened AST.
        self.active_module_path = (
            parent.active_module_path if parent is not None else None
        )
        
        if not Storage.Main:
            self.main, Storage.Main = True, self
        
        
        # clauses
        self.privacy: str = 'public'
        self.optimizers = 'dev'
        self.stacklimit = -1
        self.boot = 'none'
        if parent is None:
            self.system = system().lower()
            host_architecture = architecture()
            self._host_pointer_size = (
                8 if str(host_architecture[0]).startswith('64') else 4
            )
            self.architecture = 'auto'
            self.pointer_size = self._host_pointer_size
        else:
            self.system = parent.system
            self._host_pointer_size = parent._host_pointer_size
            self.architecture = parent.architecture
            self.pointer_size = parent.pointer_size
            self.privacy = parent.privacy
            self.optimizers = parent.optimizers
            self.stacklimit = parent.stacklimit
            self.boot = parent.boot
        
        self.namespace: dict[str, Any] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        self.methods: dict[tuple[str, str], FunctionSymbol] = {}
        self.function_scopes: dict[str, Storage] = {}
        self.types: dict[str, EnumSymbol | AggregateSymbol] = {}
        self.native_links: list[str] = []
        self.loaded_modules: list[str] = []
        self.function_aliases: dict[str, str] = {}
        self.variable_aliases: dict[str, Variable] = {}
        self.type_aliases: dict[str, str] = {}
        self.prep_sources: list[Path] = []
        self.prep_objects: list[Path] = []
        # Generated ASM path -> source metadata used to improve Clang errors.
        self.prep_metadata: dict[Path, tuple[Path, str, str, int]] = {}
        
    def define_clause(self, name: str, value: int | str | bool):
        if      name == 'Privacy': self.privacy = str(value)
        elif    name in ('Optimizations', 'Optimizers'): self.optimizers = value
        elif    name == 'System'    : self.system = value
        elif    name == 'Boot'      : self.boot = str(value).strip().lower()
        elif    name == 'Arch'      :
            self.architecture = str(value).lower()
            if self.architecture == 'auto':
                self.pointer_size = self._host_pointer_size
            else:
                target_architecture = self.architecture.split('-', 1)[0]
                self.pointer_size = 4 if target_architecture in (
                    'x86', 'i386', 'i686', 'arm', 'armv6', 'armv7',
                    'thumb', 'riscv32',
                ) else 8
        elif    name == 'StackLimit': self.stacklimit = value 
        
    def contains_local(self, name: str) -> bool:
        return name in self.namespace

    def _module_root(self) -> 'Storage':
        current = self
        while current.parent is not None:
            current = current.parent
        return current

    def _is_visible(self, symbol: object | None) -> bool:
        if symbol is None or getattr(symbol, 'privacy', 'public') != 'private':
            return symbol is not None
        origin = getattr(symbol, 'module_path', None)
        active = self._module_root().active_module_path
        return origin is None or origin == active

    def resolve(self, name: str) -> SemanticObject | None:
        symbol = self.namespace.get(name)
        if symbol is not None and self._is_visible(symbol):
            return symbol
        symbol = self.variable_aliases.get(name)
        if symbol is not None and self._is_visible(symbol):
            return symbol
        if self.parent is not None:
            if self._function_root is self and name not in self.global_names:
                return None
            return self.parent.resolve(name)
        return None

    def add(self, name: str, obj: SemanticObject) -> bool:
        if self.contains_local(name):
            return False
        self.namespace[name] = obj
        return True

    def define_function(self, symbol: FunctionSymbol) -> bool:
        if symbol.name in self.functions:
            return False
        if symbol.scope is None:
            symbol.scope = Storage(
                self.root,
                parent=self,
                scope_name=f'function:{symbol.name}',
                function_scope=True,
            )
        self.functions[symbol.name] = symbol
        self.function_scopes[symbol.name] = symbol.scope
        return True

    def define_method(self, symbol: FunctionSymbol) -> bool:
        """Register one class method by owner type and source name."""
        owner = symbol.owner_type
        source_name = symbol.source_name
        if not owner or not source_name:
            return False
        key = (owner, source_name)
        if key in self.methods or symbol.name in self.functions:
            return False
        if any(existing.name == symbol.name for existing in self.methods.values()):
            return False
        if symbol.scope is None:
            symbol.scope = Storage(
                self.root,
                parent=self,
                scope_name=f'method:{owner}.{source_name}',
                function_scope=True,
            )
        self.methods[key] = symbol
        self.function_scopes[symbol.name] = symbol.scope
        return True

    def resolve_method(self, owner: str, name: str) -> FunctionSymbol | None:
        visited: set[str] = set()
        current = owner
        while current and current not in visited:
            visited.add(current)
            symbol = self.methods.get((current, name))
            if self._is_visible(symbol):
                return symbol
            aggregate = self.resolve_type(current)
            current = getattr(aggregate, 'parent_type', None)
        if self.parent is not None:
            return self.parent.resolve_method(owner, name)
        return None

    def resolve_field(self, owner: str, name: str):
        """Resolve an aggregate field through its compile-time parent chain."""
        visited: set[str] = set()
        current = owner
        while current and current not in visited:
            visited.add(current)
            aggregate = self.resolve_type(current)
            if aggregate is None:
                break
            field = next(
                (field for field in aggregate.fields if field.name == name),
                None,
            )
            if field is not None:
                return field
            current = getattr(aggregate, 'parent_type', None)
        if self.parent is not None:
            return self.parent.resolve_field(owner, name)
        return None

    def define_type(self, symbol: EnumSymbol | AggregateSymbol) -> bool:
        """Register a type in the current type namespace."""
        if symbol.name in self.types:
            return False
        self.types[symbol.name] = symbol
        return True

    def resolve_type(self, name: str) -> EnumSymbol | AggregateSymbol | None:
        symbol = self.types.get(name)
        if symbol is not None and self._is_visible(symbol):
            return symbol
        alias = self.type_aliases.get(name)
        if alias is not None:
            symbol = self.types.get(alias)
            if symbol is not None and self._is_visible(symbol):
                return symbol
        if self.parent is not None:
            return self.parent.resolve_type(name)
        return None

    def resolve_module_value(self, name: str) -> SemanticObject | None:
        """Resolve an explicit ``global`` binding with module visibility."""
        symbol = self.namespace.get(name)
        if symbol is None:
            symbol = self.variable_aliases.get(name)
        return symbol if self._is_visible(symbol) else None

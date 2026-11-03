from pathlib import Path
import hashlib
from typing import Any

from tools import diagnostic

from core.frontend.objects import (
    AggregateSymbol,
    EnumSymbol,
    FunctionSymbol,
    OpaqueSymbol,
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
        target_key = self.storage.function_aliases.get(name)
        if target_key is not None:
            function = self.storage.functions.get(target_key)
        else:
            candidates = self.storage.function_candidates.get(name, ())
            active = getattr(current_function, 'module_path', None)
            if active is None:
                active = self.storage.active_module_path
            function = next(
                (
                    item for item in candidates
                    if getattr(item, 'module_path', None) == active
                ),
                None,
            )
            if function is None:
                function = self.storage.functions.get(name)
            if function is None and len(candidates) == 1:
                function = candidates[0]
        if function is None:
            return None
        origin = getattr(function, 'module_path', None)
        active = getattr(current_function, 'module_path', None)
        if active is None:
            active = self.storage.active_module_path
        # The flattened function table still contains source definitions for
        # every module.  Only a qualified import alias may cross that module
        # boundary; unqualified lookup must stay within the active module.
        if origin is not None and active is not None and origin != active \
                and '.' not in name and name not in self.storage.function_aliases:
            return None
        if getattr(function, 'privacy', 'public') != 'private':
            return function
        return function if origin is None or origin == active else None

    def get(self, name: str, default=None):
        function = self.resolve_for(name)
        return function if function is not None else default


class Storage(diagnostic.Diagnostics):
    Main: 'Storage | None' = None

    @staticmethod
    def _module_digest(module: object) -> str:
        """Return a process-independent suffix for flattened declarations."""
        return hashlib.sha256(str(module).encode('utf-8')).hexdigest()[:12]
    
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
        # ``prod`` is the normal compilation profile.  ``dev`` remains
        # available when inspecting Bagron's unoptimised emitted IR.
        self.optimizers = 'prod'
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
        self.method_candidates: dict[tuple[str, str], list[FunctionSymbol]] = {}
        self.function_scopes: dict[str, Storage] = {}
        self.types: dict[str, EnumSymbol | AggregateSymbol | OpaqueSymbol] = {}
        self.native_links: list[str] = []
        self.native_objects: list[Path] = []
        # Search paths declared explicitly by #link in the entry module.
        self.native_link_dirs: list[Path] = []
        self.loaded_modules: list[str] = []
        self.function_aliases: dict[str, str] = {}
        # One source spelling may legitimately occur in several imported
        # modules/packages.  ``functions`` keeps a compatibility lookup for
        # the first spelling; this index retains every semantic object.
        self.function_candidates: dict[str, list[FunctionSymbol]] = {}
        self.type_candidates: dict[str, list[object]] = {}
        self.variable_aliases: dict[str, Variable] = {}
        self.variable_candidates: dict[str, list[Variable]] = {}
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

    def _is_visible(self, symbol: object | None, name: str | None = None) -> bool:
        if symbol is None or getattr(symbol, 'privacy', 'public') != 'private':
            if symbol is None:
                return False
            origin = getattr(symbol, 'module_path', None)
            active = self._module_root().active_module_path
            return (
                origin is None
                or active is None
                or origin == active
                or getattr(symbol, 'is_method', False)
                or (
                    name is not None
                    and (
                        '.' in name
                        or name in self.variable_aliases
                        or name in self.type_aliases
                    )
                )
            )
        origin = getattr(symbol, 'module_path', None)
        active = self._module_root().active_module_path
        return origin is None or origin == active

    def resolve(self, name: str) -> SemanticObject | None:
        symbol = self.variable_aliases.get(name)
        candidates = self.variable_candidates.get(name, ())
        if symbol is None and candidates:
            active = self._module_root().active_module_path
            symbol = next(
                (
                    item for item in candidates
                    if getattr(item, 'module_path', None) == active
                ),
                None,
            )
            if symbol is None and len(candidates) == 1:
                symbol = candidates[0]
        if symbol is None:
            symbol = self.namespace.get(name)
        if symbol is not None and self._is_visible(symbol, name):
            return symbol
        if self.parent is not None:
            return self.parent.resolve(name)
        return None

    def add(self, name: str, obj: SemanticObject) -> bool:
        existing = self.namespace.get(name)
        if existing is not None:
            same_module = (
                getattr(existing, 'module_path', None)
                == getattr(obj, 'module_path', None)
            )
            if not (
                self is self._module_root()
                and getattr(existing, 'scope_kind', None) == 'global'
                and getattr(obj, 'scope_kind', None) == 'global'
                and not same_module
            ):
                return False
            module = str(getattr(obj, 'module_path', 'module'))
            storage_key = f'__source_{self._module_digest(module)}_{name}'
            suffix = 1
            while storage_key in self.namespace:
                suffix += 1
                storage_key = f'__source_{self._module_digest(module)}_{suffix}_{name}'
            self.namespace[storage_key] = obj
            self.variable_candidates.setdefault(name, []).append(obj)
            obj.storage_key = storage_key
            return True
        self.namespace[name] = obj
        if getattr(obj, 'scope_kind', None) == 'global':
            self.variable_candidates.setdefault(name, []).append(obj)
        obj.storage_key = name
        return True

    def define_function(self, symbol: FunctionSymbol) -> bool:
        candidates = self.function_candidates.setdefault(symbol.name, [])
        if any(
            getattr(existing, 'module_path', None) == getattr(symbol, 'module_path', None)
            for existing in candidates
        ):
            return False
        if symbol.scope is None:
            symbol.scope = Storage(
                self.root,
                parent=self,
                scope_name=f'function:{symbol.name}',
                function_scope=True,
            )
        if symbol.name not in self.functions:
            storage_key = symbol.name
        else:
            module = str(getattr(symbol, 'module_path', 'module'))
            storage_key = f'__source_{self._module_digest(module)}_{symbol.name}'
            suffix = 1
            while storage_key in self.functions:
                suffix += 1
                storage_key = f'__source_{self._module_digest(module)}_{suffix}_{symbol.name}'
        self.functions[storage_key] = symbol
        self.function_scopes[storage_key] = symbol.scope
        candidates.append(symbol)
        symbol.storage_key = storage_key
        return True

    def function_key(self, symbol: FunctionSymbol) -> str | None:
        for key, candidate in self.functions.items():
            if candidate is symbol:
                return key
        return None

    @staticmethod
    def _paths_match(a: object, b: object) -> bool:
        """Compare module paths taking resolution and casing into account."""
        if a is None or b is None:
            return a == b
        sa, sb = str(a), str(b)
        if sa == sb:
            return True
        try:
            return Path(sa).resolve() == Path(sb).resolve()
        except Exception:
            return sa.lower() == sb.lower()

    def resolve_variable_for_module(
        self,
        name: str,
        module_path: object | None = None,
    ) -> Variable | None:
        root = self._module_root()
        candidates = root.variable_candidates.get(name, ())
        target_path = module_path if module_path is not None else root.active_module_path
        if target_path is not None:
            for candidate in candidates:
                cand_path = getattr(candidate, 'module_path', None)
                if self._paths_match(cand_path, target_path):
                    return candidate
        if len(candidates) == 1:
            return candidates[0]
        return root.namespace.get(name)

    def resolve_function_for_module(
        self,
        name: str,
        module_path: object | None = None,
    ) -> FunctionSymbol | None:
        root = self._module_root()
        candidates = root.function_candidates.get(name, ())
        target_path = module_path if module_path is not None else root.active_module_path
        if target_path is not None:
            for candidate in candidates:
                cand_path = getattr(candidate, 'module_path', None)
                if self._paths_match(cand_path, target_path):
                    return candidate
        if len(candidates) == 1:
            return candidates[0]
        return root.functions.get(name)

    def define_method(self, symbol: FunctionSymbol) -> bool:
        """Register one class method by owner type and source name."""
        owner = symbol.owner_type
        source_name = symbol.source_name
        if not owner or not source_name:
            return False
        candidates = self.method_candidates.setdefault((owner, source_name), [])
        if any(
            getattr(existing, 'module_path', None)
            == getattr(symbol, 'module_path', None)
            for existing in candidates
        ):
            return False
        same_module_function = self.resolve_function_for_module(
            symbol.name,
            getattr(symbol, 'module_path', None),
        )
        if same_module_function is not None:
            return False
        if symbol.scope is None:
            symbol.scope = Storage(
                self.root,
                parent=self,
                scope_name=f'method:{owner}.{source_name}',
                function_scope=True,
            )
        if not candidates:
            storage_key = owner
        else:
            module = str(getattr(symbol, 'module_path', 'module'))
            digest = self._module_digest(module)
            storage_key = f'__source_{digest}_{owner}'
            suffix = 1
            while (storage_key, source_name) in self.methods:
                suffix += 1
                storage_key = f'__source_{digest}_{suffix}_{owner}'
        key = (storage_key, source_name)
        self.methods[key] = symbol
        self.function_scopes[key] = symbol.scope
        candidates.append(symbol)
        symbol.method_key = key
        return True

    def resolve_method(self, owner: str, name: str) -> FunctionSymbol | None:
        visited: set[str] = set()
        current = owner
        while current and current not in visited:
            visited.add(current)
            root = self._module_root()
            candidates = root.method_candidates.get((current, name), ())
            active = root.active_module_path
            symbol = next(
                (
                    item for item in candidates
                    if self._paths_match(getattr(item, 'module_path', None), active)
                ),
                None,
            )
            if symbol is None and len(candidates) == 1:
                symbol = candidates[0]
            if symbol is None:
                symbol = root.methods.get((current, name))
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

    def define_type(
        self,
        symbol: EnumSymbol | AggregateSymbol | OpaqueSymbol,
    ) -> bool:
        """Register a type in the current type namespace."""
        candidates = self.type_candidates.setdefault(symbol.name, [])
        if any(
            getattr(existing, 'module_path', None) == getattr(symbol, 'module_path', None)
            for existing in candidates
        ):
            return False
        if symbol.name not in self.types:
            storage_key = symbol.name
        else:
            module = str(getattr(symbol, 'module_path', 'module'))
            storage_key = f'__source_{self._module_digest(module)}_{symbol.name}'
            suffix = 1
            while storage_key in self.types:
                suffix += 1
                storage_key = f'__source_{self._module_digest(module)}_{suffix}_{symbol.name}'
        self.types[storage_key] = symbol
        symbol.registry_key = storage_key
        candidates.append(symbol)
        return True

    def resolve_type(
        self,
        name: str,
    ) -> EnumSymbol | AggregateSymbol | OpaqueSymbol | None:
        candidates = self.type_candidates.get(name, ())
        symbol = None
        if candidates:
            active = self._module_root().active_module_path
            symbol = next(
                (
                    item for item in candidates
                    if getattr(item, 'module_path', None) == active
                ),
                None,
            )
            if symbol is None and len(candidates) == 1:
                symbol = candidates[0]
        if symbol is None:
            symbol = self.types.get(name)
        if symbol is not None and self._is_visible(symbol, name):
            return symbol
        alias = self.type_aliases.get(name)
        if alias is not None:
            symbol = self.types.get(alias)
            if symbol is None:
                candidates = self.type_candidates.get(alias, ())
                if len(candidates) == 1:
                    symbol = candidates[0]
            if symbol is not None and self._is_visible(symbol, name):
                return symbol
        if self.parent is not None:
            return self.parent.resolve_type(name)
        return None

    def resolve_module_value(self, name: str) -> SemanticObject | None:
        """Resolve a module-level value with module visibility."""
        symbol = self.namespace.get(name)
        if symbol is None:
            symbol = self.variable_aliases.get(name)
        return symbol if self._is_visible(symbol, name) else None

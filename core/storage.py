from typing import Any, Literal

from tools import diagnostic

from core.frontend.objects import FunctionSymbol, Variable

from platform import system, architecture

SemanticObject = Literal[Variable]


class Storage(diagnostic.Diagnostics):
    Main: 'Storage | None' = None
    
    def __init__(self, root: str):
        self.main: bool = False
        self.root = root        
        
        if not Storage.Main:
            self.main, Storage.Main = True, self
        
        
        # clauses
        self.privacy: str = 'public'
        self.optimizers = 'dev'
        self.stacklimit = -1
        self.system = system().lower()
        self.architecture = architecture()
        self.pointer_size = 8 if str(self.architecture[0]).startswith('64') else 4
        print(self.architecture)
        
        self.namespace: dict[str, Any] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        
    def define_clause(self, name: str, value: int | str | bool):
        if      name == 'Visibility': self.privacy = str(value)
        elif    name == 'Optimizers': self.optimizers = value
        elif    name == 'System'    : self.system = value
        elif    name == 'Arch'      :
            self.architecture = value
            self.pointer_size = 4 if value == 'x86' else 8
        elif    name == 'StackLimit': self.stacklimit = value 
        
    def add(self, name: str, obj: SemanticObject):
        self.namespace[name] = obj

    def define_function(self, symbol: FunctionSymbol):
        self.functions[symbol.name] = symbol

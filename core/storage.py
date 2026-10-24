from typing import Any, Literal

from tools import diagnostic

from core.frontend.EASYC.objects import Variable

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
        print(self.architecture)
        
        self.namespace: dict[str, Any] = {}
        
    def define_clause(self, name: str, value: int | str | bool):
        if      name == 'Visibility': self.privacy = str(value)
        elif    name == 'Optimizers': self.optimizers = value
        elif    name == 'System'    : self.system = value
        elif    name == 'Arch'      : self.architecture = value
        elif    name == 'StackLimit': self.stacklimit = value 
        
    def add(self, name: str, obj: SemanticObject):
        self.namespace[name] = obj
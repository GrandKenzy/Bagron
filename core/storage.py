from typing import Any

from tools import diagnostic

from platform import system, architecture

class Storage(diagnostic.Diagnostics):
    Main: 'Storage | None' = None
    
    def __init__(self, root: str):
        self.main: bool = False
        self.root = root        
        
        if not Storage.Main:
            self.main, Storage.Main = True, self
        
        
        # clauses
        self.privacy = 'public'
        self.optimizers = 'dev'
        self.stacklimit = -1
        self.system = system().lower()
        self.architecture = architecture()
        print(self.architecture)
        
        self.namespace: dict[str, Any] = {}
        
    def define_clause(self, name: str, value: int | str | bool):
        if      name == 'Visibility': self.privacy = value
        elif    name == 'Optimizers': self.optimizers = value
        elif    name == 'System'    : self.system = value
        elif    name == 'Arch'      : self.architecture = value
        elif    name == 'StackLimit': self.stacklimit = value 
from typing import Any

from tools import diagnostic


class Storage(diagnostic.Diagnostics):
    Main: 'Storage | None' = None
    
    def __init__(self, root: str):
        self.main: bool = False
        self.root = root        
        
        if not Storage.Main:
            self.main, Storage.Main = True, self
        
        
        
        self.namespace: dict[str, Any] = {}
        
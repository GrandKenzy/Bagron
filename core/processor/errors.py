from typing import Any

class UnknownASTNodeError(Exception):
    def __init__(self, node: Any, message: str | None = None):
        self.node = node
        self.node_name = getattr(node, 'name', str(node))
        tokens = getattr(node, 'all_tokens', getattr(node, 'tokens', []))
        first_tok = tokens[0] if tokens else None
        self.line = getattr(first_tok, 'line', None)
        self.col = getattr(first_tok, 'col', None)
        pos = f" (línea {self.line}, col {self.col})" if self.line is not None else ""
        msg = message or f"Nodo AST desconocido o no soportado '{self.node_name}'{pos}. No existe un visitor definido para procesarlo en el procesador semántico."
        super().__init__(msg)

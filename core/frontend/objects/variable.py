from typing import Any


class Variable:
    def __init__(self, name: str, t: str, pointer_level: int, value: Any):
        self.name = name
        self.type = t
        self.pointer_level = pointer_level
        self.value = value
        
        self.is_const = False
        self.value_is_const = False
        self.pointer_is_const = False
        self.call_signature = None
        self.pointer_size = None
        self.bit_width = None
        self.signed = None

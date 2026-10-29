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
        self.type_spec = None
        self.value_info = None
        self.initialized = value is not None
        self.privacy = 'public'
        self.scope_kind = 'global'
        self.is_for_iterator = False
        self.is_receiver = False
        self.uses_frontend_initializer = False

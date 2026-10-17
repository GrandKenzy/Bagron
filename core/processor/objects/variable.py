from typing import Any, Literal

from core.processor.objects.array import Array
from core.processor.objects.base import Object


class Variable(Object):
    __slots__ = (
        'array',
        'c_name',
        'fixed_size',
        'is_constant',
        'is_cptr',
        'is_main',
        'is_ptr',
        'name',
        'privacy',
        'ref',
        'type',
        'value'
    )

    def __init__(
        self,
        name: str,
        value: Any,
        type: str,
        privacy: Literal['public', 'private'] = 'public',
        is_constant: bool = False,
        is_cptr: bool = False,
        is_ptr: bool = False,
        array: Array | None = None,
        c_name: str | None = None,
        is_main: bool = False 
    ):
        super().__init__()
        self.name = name
        self.c_name: str = c_name if c_name is not None else name
        self.value = value
        self.privacy = privacy
        self.ref: bool = False
        self.is_cptr: bool = is_cptr or type == 'cptr'
        self.is_ptr: bool = is_ptr or type == 'ptr'
        self.type = 'void' if type in ('cptr', 'ptr') else type
        self.is_constant = is_constant or self.is_cptr
        self.is_main = is_main
        self.fixed_size: int | None = array.size if array is not None else None
        self.array: Array | None = array

    def is_valid(self) -> bool:
        if self.type == 'type': return False
        if self.in_scope: return self.uses > 0
        return not (self.privacy == 'private' and self.uses == 0)

    def __repr__(self) -> str:
        arr_str = f", array={self.array!r}" if self.array is not None else ""
        cptr_str = ", is_cptr=True" if self.is_cptr else ""
        ptr_str = ", is_ptr=True" if self.is_ptr else ""
        return f"Variable(name={self.name!r}, type={self.type!r}, privacy={self.privacy!r}, const={self.is_constant}{cptr_str}{ptr_str}{arr_str})"

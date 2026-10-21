from core.processor.objects.base import Object


class Array(Object):
    __slots__ = (
        'element_type',
        'size',
        'is_cptr',
        'is_ptr',
        'is_pointer',
        'pointer_base_type',
    )

    def __init__(
        self,
        element_type: str,
        size: int | None = None,
        is_cptr: bool = False,
        is_ptr: bool = False,
        pointer_base_type: str | None = None,
    ):
        super().__init__()
        self.is_cptr: bool = is_cptr or element_type == 'cptr'
        self.is_ptr: bool = is_ptr or element_type == 'ptr'
        self.element_type: str = 'void' if element_type in ('cptr', 'ptr') else element_type
        self.size: int | None = size
        self.pointer_base_type: str | None = pointer_base_type or (self.element_type if (self.is_cptr or self.is_ptr) else None)
        self.is_pointer: bool = self.is_cptr or self.is_ptr or self.element_type.endswith('*')

    def __repr__(self) -> str:
        size_str = f", size={self.size}" if self.size is not None else ""
        ptr_str = ", is_cptr=True" if self.is_cptr else (", is_ptr=True" if self.is_ptr else "")
        return f"Array(element_type={self.element_type!r}{size_str}{ptr_str})"

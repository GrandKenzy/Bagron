from typing import Literal
from core.processor.objects.base import Object


class StructField:
    __slots__ = ('name', 'type', 'bits', 'fixed_size')

    def __init__(self, name: str, type: str, bits: int | None = None, fixed_size: int | None = None):
        self.name = name
        self.type = type
        self.bits = bits
        self.fixed_size = fixed_size

    def __repr__(self) -> str:
        bit_str = f" : {self.bits}" if self.bits is not None else ""
        return f"{self.type} {self.name}{bit_str}"


class StructDecl(Object):
    __slots__ = (
        'name',
        'c_name',
        'fields',
        'field_map',
        'privacy',
        'is_packed',
        'is_volatile',
        'align',
        'kind',
        'scoped',
    )

    def __init__(
        self,
        name: str,
        fields: list[StructField] | None = None,
        privacy: Literal['public', 'private'] = 'public',
        is_packed: bool = False,
        is_volatile: bool = False,
        align: int | str | None = None,
        kind: Literal['struct', 'flags', 'mold'] = 'struct',
        in_scope: Object | None = None,
        scoped: Any = None,
        c_name: str | None = None,
    ):
        super().__init__()
        self.name = name
        self.c_name: str = c_name if c_name is not None else name
        self.fields = fields or []
        self.field_map: dict[str, StructField] = {f.name: f for f in self.fields if f.name}
        self.privacy = privacy
        self.is_packed = is_packed
        self.is_volatile = is_volatile
        self.align = align
        self.kind = kind
        self.in_scope = in_scope
        self.scoped = scoped

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        attrs = []
        if self.is_packed:
            attrs.append('packed')
        if self.is_volatile:
            attrs.append('volatile')
        if self.align:
            attrs.append(f'align={self.align}')
        attr_str = f" [{', '.join(attrs)}]" if attrs else ""
        return f"StructDecl(name={self.name!r}, kind={self.kind!r}, fields={self.fields}{attr_str}, privacy={self.privacy!r})"


__all__ = [
    'StructField',
    'StructDecl',
]

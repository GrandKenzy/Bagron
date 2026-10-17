from core.processor.objects.base import Object


class TypeAlias(Object):
    __slots__ = ('name', 'target_type', 'privacy')

    def __init__(self, name: str, target_type: str, privacy: str = 'public'):
        super().__init__()
        self.name = name
        self.target_type = target_type
        self.privacy = privacy

    @property
    def target(self) -> str:
        return self.target_type

    def is_valid(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f'TypeAlias(name={self.name}, target={self.target_type}, privacy={self.privacy})'


# Alias para retrocompatibilidad
TypeDecl = TypeAlias

__all__ = [
    'TypeAlias',
    'TypeDecl',
]

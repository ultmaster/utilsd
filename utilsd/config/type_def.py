import os
import typeguard
from pathlib import Path, PosixPath
from typing import Any, Optional, Type, TypeVar, Generic, Union, List, Tuple

from .registry import Registry

T = TypeVar('T')

class TypeDefRegistry(metaclass=Registry, name='type_def'):
    pass


class TypeDef(Generic[T]):
    """Base class for type definitions.

    Each type should specify how what kind of types they intend to handle,
    as well as the serialization that dumps to payload and loads from payload.

    Dump: convert into a plain format, that can be directly serialized with ``json.dumps`` or ``yaml.dump``.
    Load: Load from a plain format, convert it to a complex object with proper validation.

    For subclass override, it is recommended to override ``from_plain`` and ``to_plain``.
    The default ``validate()`` with typeguard should work for most cases.
    All TypeError and ValueError raised from ``from_plain`` and ``to_plain`` and ``validate`` will be caught,
    and raise again with proper metadata in the base class.

    The overridden method is only called when ``new()`` returns not null.
    """

    def __init__(self, type_: Type[T]) -> None:
        self.type = type_

    def validate(self, converted: T) -> None:
        # when something goes wrong, check_type raises TypeError
        typeguard.check_type(..., converted, self.type)

    @classmethod
    def new(cls, type_: Type) -> Optional['TypeDef']:
        return None

    def from_plain(self, plain: Any) -> T:
        return plain

    def to_plain(self, obj: T) -> Any:
        return obj

    @staticmethod
    def dump(type_def: Type[T], obj: T) -> Any:
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                try:
                    return t.to_plain(obj)
                except (TypeError, ValueError) as e:
                    ...
        raise TypeError(f'No hook found for type definition: {type_def}')

    @staticmethod
    def load(type_def: Type[T], payload: Any) -> T:
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                try:
                    converted = t.from_plain(payload)
                    t.validate(converted)
                    return converted
                except (TypeError, ValueError) as e:
                    ...
        raise TypeError(f'No hook found for type definition: {type_def}')


@TypeDefRegistry.register_module()
class AnyDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if type_ is Any:
            return cls(type_)
        return None

    def from_plain(self, plain):
        return plain

    def to_plain(self, obj):
        return obj


@TypeDefRegistry.register_module()
class OptionalDef(TypeDef):
    @classmethod
    def new(cls, type_):
        self = cls(type_)
        if str(type_).startswith('typing.Optional['):
            self.inner_type = type.__args__[0]
        elif getattr(type_, '__origin__', None) == Union and type_.__args__[1] == type(None):
            self.inner_type = type.__args__[0]
        else:
            return None
        return self

    def from_plain(self, plain):
        return TypeDef.load(self.inner_type, plain)

    def to_plain(self, obj):
        if obj is None:
            return None
        return TypeDef.dump(self.inner_type, obj)


@TypeDefRegistry.register_module()
class PathDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if type_ in (Path, PosixPath, os.PathLike):
            return cls(type_)
        return None

    def from_plain(self, plain):
        return Path(plain)

    def to_plain(self, obj):
        return str(obj)


@TypeDefRegistry.register_module()
class ListDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in [list, List]:
            self = cls(type_)
            self.inner_type = type_.__args__[0]
            return self
        elif type_ == list:
            raise TypeError('Please use `List[Any]` instead of list.')
        return None

    def from_plain(self, plain):
        if not isinstance(plain, list):
            raise ValueError(f'Expected a list, found {type(plain)}: {plain}')
        return [TypeDef.load(self.inner_type, value) for value in plain]

    def to_plain(self, obj):
        return [TypeDef.dump(self.inner_type, value) for value in obj]


class TupleDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in [tuple, Tuple]:
            self = cls(type_)
            self.inner_types = type_.__args__
            return self
        elif type_ == list:
            raise TypeError('Please use `List[Any]` instead of list.')
        return None

    def from_plain(self, plain):
        if not isinstance(plain, (list, tuple)):
            raise ValueError(f'Expected a list or a tuple, found {type(plain)}: {plain}')
        return tuple([TypeDef.load(type, value) for type, value in zip(self.inner_types, plain)])

    def to_plain(self, obj):
        return [TypeDef.dump(self.inner_type, value) for value in obj]


class DictDef(TypeDef):

# class UnionDef(TypeDef):

# class PrimitiveDef(TypeDef):

# class EnumDef(TypeDef):


class DataclassDef(TypeDef):

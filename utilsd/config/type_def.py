"""
Convert to / from a plain-type python object to a complex type,
with type-checking/conversion based on type annotations.
"""

import dataclasses
import functools
import os
from contextlib import contextmanager
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, Optional, Type, TypeVar, Generic, Union, List, Tuple

import typeguard

from .exception import ValidationError
from .registry import Registry

T = TypeVar('T')


class TypeDefRegistry(metaclass=Registry, name='type_def'):
    pass


class ParseContext:
    """Necessary information to generate accurate error message."""

    def __init__(self):
        self.path: List[str] = []
        self.matches: List[List[str]] = []

    @contextmanager
    def onto(self, name):
        self.path.append(name)
        self.matches.append([])
        try:
            yield
        finally:
            self.path.pop()
            self.matches.pop()

    @contextmanager
    def match_type(self, type):
        self.matches[-1].append(type)
        try:
            yield
        finally:
            self.matches[-1].pop()

    @property
    def message(self) -> Tuple[str]:
        return (
            ' -> '.join(self.path) + '\n',
            ' -> '.join(self.matches[-1]) + '\n',
        )


def pass_context(func):
    """Pass context object for subclassed processors"""
    @functools.wraps
    def wrapper(*args, **kwargs):
        return func(*args, ctx=kwargs.get('ctx'), **kwargs)
    return wrapper


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

    def from_plain(self, plain: Any, ctx: Optional[ParseContext] = None) -> T:
        return plain

    def to_plain(self, obj: T, ctx: Optional[ParseContext] = None) -> Any:
        return obj

    @staticmethod
    def dump(type_def: Type[T], obj: T, ctx: Optional[ParseContext] = None) -> Any:
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                try:
                    return t.to_plain(obj, ctx=ctx)
                except (TypeError, ValueError) as e:
                    # add message for location here
                    err_message = 'Object can not be dumped.'
                    if ctx is not None and ctx.formatted_path:
                        err_message += ' Cause: ' + ctx.formatted_path
                    raise ValidationError(err_message)
        raise TypeError(f'No hook found for type definition: {type_def}')

    @staticmethod
    def load(type_def: Type[T], payload: Any, ctx: Optional[ParseContext] = None) -> T:
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                try:
                    converted = t.from_plain(payload, ctx=ctx)
                    t.validate(converted)
                    return converted
                except (TypeError, ValueError) as e:
                    err_message = 'Object can not be loaded.'
                    if ctx is not None and ctx.formatted_path:
                        err_message += ' Cause: ' + ctx.formatted_path
                    raise ValidationError(err_message)
        raise TypeError(f'No hook found for type definition: {type_def}')


class AnyDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if type_ is Any:
            return cls(type_)
        return None

    def from_plain(self, plain, ctx=None):
        # no need to pass context here
        return plain

    def to_plain(self, obj, ctx=None):
        return obj


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

    def from_plain(self, plain, ctx=ctx):
        return TypeDef.load(self.inner_type, plain, ctx=ctx)

    def to_plain(self, obj):
        if obj is None:
            return None
        return TypeDef.dump(self.inner_type, obj, ctx=ctx)


class PathDef(TypeDef):
    pathlike = (Path, PosixPath, os.PathLike)

    @classmethod
    def new(cls, type_):
        if type_ in cls.pathlike:
            return cls(type_)
        return None

    def from_plain(self, plain):
        return Path(plain)

    def to_plain(self, obj):
        if not isinstance(obj, self.pathlike):
            raise ValueError(f'Expected a tuple, found {type(obj)}: {obj}')
        return str(obj)


class ListDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (list, List):
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
        if not isinstance(obj, list):
            raise ValueError(f'Expected a list, found {type(obj)}: {obj}')
        return [TypeDef.dump(self.inner_type, value) for value in obj]


class TupleDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (tuple, Tuple):
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
        if not isinstance(obj, tuple):
            raise ValueError(f'Expected a tuple, found {type(obj)}: {obj}')
        return [TypeDef.dump(self.inner_type, value) for value in obj]


class DictDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (dict, Dict):
            self = cls(type_)
            self.key_type = type_.__args__[0]
            self.value_type = type_.__args__[1]
            return self
        elif type_ == list:
            raise TypeError('Please use `List[Any]` instead of list.')
        return None

    def from_plain(self, plain):
        if not isinstance(plain, dict):
            raise ValueError(f'Expected a dict, found {type(plain)}: {plain}')
        return {
            TypeDef.load(self.key_type, key): TypeDef.load(self.value_type, value)
            for key, value in plain.items()
        }

    def to_plain(self, obj):
        if not isinstance(obj, dict):
            raise ValueError(f'Expected a dict, found {type(obj)}: {obj}')
        return {
            TypeDef.dump(self.key_type, key): TypeDef.dump(self.value_type, value)
            for key, value in obj.items()
        }


class EnumDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if isinstance(type_, type) and issubclass(type_, Enum):
            return cls(type_)
        return None

    def from_plain(self, plain):
        return self.type(plain)

    def to_plain(self, obj):
        if not isinstance(obj, self.type):
            raise ValueError(f'Expected a enum of {self.type}, found {obj}')
        return obj.value


class UnionDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__original__', None) == Union:
            self = cls(type_)
            self.inner_types = list(type_.__args__)
        return None

    def from_plain(self, plain):
        # try types in union one by one, skip when validation error
        # until exhausted
        def _try_types(types):
            if not types:
                raise ValueError(f'Possible types from union {self.inner_types} is exhausted.')
            try:
                return TypeDef.load(types[0], plain)
            except ValidationError:
                return _try_types(types[1:])

        return _try_types(self.inner_types)

    def to_plain(self, obj):
        def _try_types(types):
            if not types:
                raise ValueError(f'Possible types from union {self.inner_types} is exhausted.')
            try:
                return TypeDef.dump(types[0], obj)
            except ValidationError:
                return _try_types(types[1:])

        return _try_types(self.inner_types)


class PrimitiveDef(TypeDef):
    primitive_types = (int, float, str, bool)

    @classmethod
    def new(cls, type_):
        if type_ in cls.primitive_types:
            return cls(type_)
        return None

    def from_plain(self, plain):
        # support implicit conversion here
        if not isinstance(plain, self.primitive_types):
            raise ValueError(f'Cannot implicitly cast a variable with type {type(plain)}'
                             f' to {self.primitive_types}: {plain}')
        if issubclass(self.type_, float):
            return float(plain)
        if issubclass(self.type_, (int, bool)):
            # check converting to int is not numerically equal
            # to avoid mistakenly converting float to int
            if int(plain) != plain:
                raise ValueError(f'Cannot implicitly cast float {plain} to int or bool')
            return int(plain)
        return self.type_(plain)

    def to_plain(self, obj):
        if not isinstance(obj, self.type):
            raise ValueError(f'Expected {self.type}, found {obj} (type: {type(obj)}')
        return obj


class DataclassDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if dataclasses.is_dataclass(type_):
            return cls(type_)
        return None

    @staticmethod
    def _is_missing(obj: Any) -> bool:
        return isinstance(obj, type(dataclasses.MISSING))

    def from_plain(self, plain):
        if not isinstance(plain, self.primitive_types):
            raise ValueError(f'Expect a dict, but found {type(plain)}: {plain}')
        self._meta = plain.pop('_meta', None)
        class_name = type(self).__name__
        for field in dataclasses.fields(self):
            value = kwargs.pop(field.name, field.default)
            if value is not None and not self._is_missing(value):
                value = TypeDef.load(field.type, value)
            setattr(self, field.name, value)
        if kwargs:
            cls = type(self).__name__
            fields = ', '.join(kwargs.keys())
            raise ValidationError(f'{cls}: Unrecognized fields {fields}')
        self.validate()
        # support implicit conversion here
        if not isinstance(plain, self.primitive_types):
            raise ValueError(f'Cannot implicitly cast a variable with type {type(plain)}'
                             f' to {self.primitive_types}: {plain}')
        if issubclass(self.type_, float):
            return float(plain)
        if issubclass(self.type_, (int, bool)):
            # check converting to int is not numerically equal
            # to avoid mistakenly converting float to int
            if int(plain) != plain:
                raise ValueError(f'Cannot implicitly cast float {plain} to int or bool')
            return int(plain)
        return self.type_(plain)

    def to_plain(self, obj):
        if not isinstance(obj, self.type):
            raise ValueError(f'Expected {self.type}, found {obj} (type: {type(obj)}')
        return obj


# register all the modules in this file
TypeDefRegistry.register_module(module=AnyDef)
TypeDefRegistry.register_module(module=OptionalDef)
TypeDefRegistry.register_module(module=PathDef)

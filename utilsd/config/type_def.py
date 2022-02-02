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
        self.matches: List[List[str]] = [[]]

    @contextmanager
    def onto(self, name):
        """Append message for a new level. e.g.,
        a new key in dict/list, a new level in dataclass.
        """
        self.path.append(name)
        self.matches.append([])
        try:
            yield
        finally:
            self.path.pop()
            self.matches.pop()

    @contextmanager
    def match(self, type):
        """Append message for a new match. e.g.,
        Going forward in optional, another option in union.
        """
        self.matches[-1].append(type)
        try:
            yield
        finally:
            self.matches[-1].pop()

    @property
    def message(self) -> Optional[Tuple[str]]:
        if not self.path:
            return None
        return (
            ' -> '.join(self.path),
            ' -> '.join(self.matches[-1]) if self.matches[-1] else 'empty',
        )

    @property
    def current_name(self) -> str:
        if not self.path:
            return '<unnamed>'
        return self.path[-1]


class TypeDef(Generic[T]):
    """Base class for type definitions.

    Each type should specify how what kind of types they intend to handle,
    as well as the serialization that dumps to payload and loads from payload.
    The loaded type is **guaranteed** to match the annotated types.

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

    def validate(self, name: str, converted: T) -> None:
        # when something goes wrong, check_type raises TypeError
        typeguard.check_type(name, converted, self.type)

    @classmethod
    def new(cls, type_: Type) -> Optional['TypeDef']:
        raise NotImplementedError()

    def from_plain(self, plain: Any, ctx: ParseContext) -> T:
        raise NotImplementedError()

    def to_plain(self, obj: T, ctx: ParseContext) -> Any:
        raise NotImplementedError()

    @staticmethod
    def dump(type_def: Type[T], obj: T, ctx: Optional[ParseContext] = None) -> Any:
        if ctx is None:
            ctx = ParseContext
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                def_name = subclass.__name__.lower()
                if def_name.endswith('def'):
                    def_name = def_name[:-3]
                try:
                    with ctx.match(def_name):
                        return t.to_plain(obj, ctx)
                except (TypeError, ValueError) as e:
                    # add message for location here
                    err_message = 'Object can not be dumped.'
                    if ctx.message:
                        err_message += ' Cause:\n  Parsing: ' + \
                            ctx.message[0] + '\n  Matched types: ' + \
                            ctx.message[1] + '\n  Object: ' + str(obj)
                    raise ValidationError(err_message)
        raise TypeError(f'No hook found for type definition: {type_def}')

    @staticmethod
    def load(type_def: Type[T], payload: Any, ctx: Optional[ParseContext] = None) -> T:
        for subclass in TypeDefRegistry.values():
            t = subclass(type_def)
            if t is not None:
                # found a handler
                # get its name, e.g., optional, any, path
                def_name = subclass.__name__.lower()
                if def_name.endswith('def'):
                    def_name = def_name[:-3]
                try:
                    with ctx.match(def_name):
                        converted = t.from_plain(payload, ctx)
                        t.validate(ctx.current_name, converted)
                        return converted
                except (TypeError, ValueError) as e:
                    err_message = 'Object can not be loaded.'
                    if ctx.message:
                        err_message += ' Cause:\n  Parsing: ' + \
                            ctx.message[0] + '\n  Matched types: ' + \
                            ctx.message[1] + '\n  Object: ' + str(payload)
                    raise ValidationError(err_message)
        raise TypeError(f'No hook found for type definition: {type_def}')


class AnyDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if type_ is Any:
            return cls(type_)
        return None

    def from_plain(self, plain, ctx):
        return plain

    def to_plain(self, obj, ctx):
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

    def from_plain(self, plain, ctx):
        return TypeDef.load(self.inner_type, plain, ctx=ctx)

    def to_plain(self, obj, ctx):
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

    def from_plain(self, plain, ctx):
        return Path(plain)

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.pathlike):
            raise ValueError(f'Expected a tuple, found {type(obj)}: {obj}')
        return str(obj)


class ListDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (list, List):
            self = cls(type_)
            # e.g., List[int]
            self.inner_type = type_.__args__[0]
            return self
        elif issubclass(type_, list):
            raise TypeError('Please use `List[Any]` instead of list.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, list):
            raise ValueError(f'Expected a list, found {type(plain)}: {plain}')
        result = []
        for i, value in enumerate(plain):
            with ctx.onto(f'index:{i}'):
                result.append(TypeDef.load(self.inner_type, value))
        return result

    def to_plain(self, obj, ctx):
        if not isinstance(obj, list):
            raise ValueError(f'Expected a list, found {type(obj)}: {obj}')
        result = []
        for i, value in enumerate(obj):
            with ctx.onto(f'index:{i}'):
                result.append(TypeDef.dump(self.inner_type, value))
        return result


class TupleDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (tuple, Tuple):
            self = cls(type_)
            # e.g., Tuple[int, str, float]
            self.inner_types = type_.__args__
            return self
        elif issubclass(type_, tuple):
            raise TypeError('Please use `Tuple[xxx]` instead of tuple.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, (list, tuple)):
            raise ValueError(f'Expected a list or a tuple, found {type(plain)}: {plain}')
        result = []
        for i, value in enumerate(plain):
            with ctx.onto(f'index:{i}'):
                result.append(TypeDef.load(self.inner_type, value))
        return tuple(result)

    def to_plain(self, obj, ctx):
        if not isinstance(obj, tuple):
            raise ValueError(f'Expected a tuple, found {type(obj)}: {obj}')
        result = []
        for i, value in enumerate(obj):
            with ctx.onto(f'index:{i}'):
                result.append(TypeDef.dump(self.inner_type, value))
        return tuple(result)


class DictDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (dict, Dict):
            self = cls(type_)
            # e.g., Dict[str, int]
            self.key_type = type_.__args__[0]
            self.value_type = type_.__args__[1]
            return self
        elif issubclass(type_, dict):
            raise TypeError('Please use `Dict[xxx, xxx]` instead of dict.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, dict):
            raise ValueError(f'Expected a dict, found {type(plain)}: {plain}')
        result = {}
        for key, value in plain.items():
            with ctx.onto(f'key:{key}'):
                key = TypeDef.load(self.key_type, key)
            with ctx.onto(str(key)):
                value = TypeDef.load(self.value_type, value)
            result[key] = value

    def to_plain(self, obj, ctx):
        if not isinstance(obj, dict):
            raise ValueError(f'Expected a dict, found {type(obj)}: {obj}')
        result = {}
        for key, value in obj.items():
            with ctx.onto(f'key:{key}'):
                key = TypeDef.dump(self.key_type, key)
            with ctx.onto(str(key)):
                value = TypeDef.dump(self.value_type, value)
            result[key] = value
        return result


class EnumDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if isinstance(type_, type) and issubclass(type_, Enum):
            return cls(type_)
        return None

    def from_plain(self, plain, ctx):
        return self.type(plain)

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.type):
            raise ValueError(f'Expected a enum ({self.type}), found {obj}')
        return obj.value


class UnionDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__original__', None) == Union:
            self = cls(type_)
            self.inner_types = list(type_.__args__)
        return None

    def from_plain(self, plain, ctx):
        # try types in union one by one, skip when validation error
        # until exhausted
        def _try_types(types):
            if not types:
                raise ValueError(f'Possible types from union {self.inner_types} is exhausted.')
            try:
                with ctx.match(f'union:{types[0].__name__}'):
                    return TypeDef.load(types[0], plain)
            except ValidationError:
                return _try_types(types[1:])

        return _try_types(self.inner_types)

    def to_plain(self, obj, ctx):
        def _try_types(types):
            if not types:
                raise ValueError(f'Possible types from union {self.inner_types} is exhausted.')
            try:
                with ctx.match(f'union:{types[0].__name__}'):
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
            raise ValueError(f'Expected {self.type}, found {obj} (type: {type(obj)})')
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

    def validate(self, name, converted):
        for field in dataclasses.fields(converted):
            typeguard.check_type(f'{name} -> {field.name}',
                                 getattr(converted, field.name),
                                 field.type)

    def from_plain(self, plain, ctx):
        if not isinstance(plain, dict):
            raise ValueError(f'Expect a dict, but found {type(plain)}: {plain}')
        # the content with name `_meta` is ignored
        # it is reserved for writing comments
        _meta = plain.pop('_meta', None)
        kwargs = {}
        for field in dataclasses.fields(self.type_):
            # get the values with content, otherwise default
            value = plain.pop(field.name, field.default)
            # if no default value exists
            if self._is_missing(value):
                # throw error early
                raise ValueError('Expected value for `{field}`, but it is not set')
            with ctx.onto(field.name):
                value = TypeDef.load(field.type, value)
            kwargs[field.name] = value
        if plain:
            fields = ', '.join(plain.keys())
            raise ValueError(f'{self.type_.__name__}: Unrecognized fields {fields}')

        # creating dataclass
        inst = self.type_(**kwargs)
        inst._meta = _meta
        return inst

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.type):
            raise ValueError(f'Expected {self.type}, found {obj} (type: {type(obj)})')
        result = {}
        for field in dataclasses.fields(obj):
            with ctx.onto(field.name):
                result[field.name] = TypeDef.dump(field.type, value)
        return result


# register all the modules in this file
TypeDefRegistry.register_module(module=AnyDef)
TypeDefRegistry.register_module(module=OptionalDef)
TypeDefRegistry.register_module(module=PathDef)

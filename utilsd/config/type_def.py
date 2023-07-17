"""
Convert to / from a plain-type python object to a complex type,
with type-checking/conversion based on type annotations.
"""

import copy
import dataclasses
import inspect
import os
from contextlib import contextmanager
from enum import Enum
from pathlib import Path, PosixPath
from typing import (
    Any, Dict, Generic, Iterable, List, Optional, Tuple, Type,
    TypeVar, Union
)

import typeguard

from .cli_parser import CliContext
from .exception import ValidationError
from .registry import (ClassConfig, Registry, RegistryConfig, SubclassConfig,
                       dataclass_from_class)

T = TypeVar('T')

primitive_types = (int, float, str, bool)


class TypeDefRegistry(metaclass=Registry, name='type_def'):
    pass


class ParseContext:
    """Necessary information to:

    1. generate accurate error message.
    2. generate cli parser.
    """

    def __init__(self, cli_context: Optional[CliContext] = None):
        self.path: List[Union[int, str]] = []
        self.matches: List[List[str]] = [[]]
        self.cli_context = cli_context

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

    def mark_cli_anchor_point(self, type_: Type) -> None:
        """Mark an anchor point so that the cli context knows.
        This is used to simplify code.
        See the implementation for how to use it.
        """
        name = self.current_path
        if not name or any(cha in name for cha in '():'):
            # special names like '(key)xxx' cannot be added to parser
            return
        if self.cli_context is not None:
            self.cli_context.add_argument(name, type_)

    @property
    def message(self) -> Optional[Tuple[str]]:
        return (
            ' -> '.join(map(lambda x: f'index:{x}' if isinstance(x, int) else x, self.path)) \
                if self.path else '<root>',
            ' -> '.join(self.matches[-1]) if self.matches[-1] else 'empty',
        )

    @property
    def current_name(self) -> str:
        if not self.path:
            return '<unnamed>'
        if isinstance(self.path[-1], int):
            return 'index:' + str(self.path[-1])
        return self.path[-1]

    @property
    def current_path(self) -> str:
        """The "path", separated with ".".
        e.g., runtime.prep.seed
        """
        if not self.path:
            return ''
        return '.'.join(map(str, self.path))

    def __repr__(self):
        return f'ParseContext(path={self.path}, matches={self.matches})'


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

    def validate(self, converted: T, ctx: ParseContext) -> None:
        # when something goes wrong, check_type raises TypeError
        # however, in most cases, error throws earlier than this
        typeguard.check_type(f'{converted} ({ctx.current_name})', converted, self.type)

    @classmethod
    def new(cls, type_: Type) -> Optional['TypeDef']:
        raise NotImplementedError()

    def from_plain(self, plain: Any, ctx: ParseContext) -> T:
        raise NotImplementedError()

    def to_plain(self, obj: T, ctx: ParseContext) -> Any:
        raise NotImplementedError()

    @staticmethod
    def dump(type: Type[T], obj: T, ctx: Optional[ParseContext] = None) -> Any:
        if ctx is None:
            ctx = ParseContext()
        for subclass in TypeDefRegistry.module_dict.values():
            t = subclass.new(type)
            if t is not None:
                # found a handler
                def_name = subclass.__name__.lower()
                if def_name.endswith('def'):
                    def_name = def_name[:-3]
                with ctx.match(def_name):
                    try:
                        return t.to_plain(obj, ctx)
                    except (TypeError, ValueError, ImportError) as e:
                        # add message for location here
                        err_message = 'Object can not be dumped.'
                        if ctx.message:
                            err_message += ' Cause: ' + str(e) + '\n  Parser location: ' + \
                                ctx.message[0] + '\n  Matched types: ' + \
                                ctx.message[1] + '\n  Object: ' + str(obj)
                        raise ValidationError(err_message)
        raise TypeError(f'No hook found for type: {type}')

    @staticmethod
    def load(type: Type[T], payload: Any, ctx: Optional[ParseContext] = None) -> T:
        if ctx is None:
            ctx = ParseContext()
        for subclass in TypeDefRegistry.module_dict.values():
            t = subclass.new(type)
            if t is not None:
                # found a handler
                # get its name, e.g., optional, any, path
                def_name = subclass.__name__.lower()
                if def_name.endswith('def'):
                    def_name = def_name[:-3]
                with ctx.match(def_name):
                    try:
                        converted = t.from_plain(payload, ctx)
                        t.validate(converted, ctx)
                        return converted
                    except (TypeError, ValueError, ImportError) as e:
                        err_message = 'Object can not be loaded.'
                        if ctx.message:
                            err_message += ' Cause: ' + str(e) + '\n  Parser location: ' + \
                                ctx.message[0] + '\n  Matched types: ' + \
                                ctx.message[1] + '\n  Object: ' + str(payload)
                        raise ValidationError(err_message)
        raise TypeError(f'No hook found for type: {type}')


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


class NoneTypeDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if type_ is type(None):
            return cls(type_)
        return None

    def from_plain(self, plain, ctx):
        ctx.mark_cli_anchor_point(type(None))
        return plain

    def to_plain(self, obj, ctx):
        if obj is None:
            return None
        else:
            raise TypeError(f'Expected None, got {obj}')


class OptionalDef(TypeDef):
    @classmethod
    def new(cls, type_):
        self = cls(type_)
        if str(type_).startswith('typing.Optional['):
            self.inner_type = type_.__args__[0]
        elif getattr(type_, '__origin__', None) == Union and type_.__args__[1] == type(None):
            self.inner_type = type_.__args__[0]
        else:
            return None
        return self

    def from_plain(self, plain, ctx):
        if plain is None:
            # if inner type is one of primitives,
            # add a marker for cli
            if self.inner_type in primitive_types:
                ctx.mark_cli_anchor_point(self.inner_type)
            return None
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
        path = Path(plain)
        ctx.mark_cli_anchor_point(str)
        return path

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.pathlike):
            raise TypeError(f'Expect a tuple, found {type(obj)}: {obj}')
        return str(obj)


class ListDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (list, List):
            self = cls(type_)
            # e.g., List[int]
            self.inner_type = type_.__args__[0]
            return self
        elif inspect.isclass(type_) and issubclass(type_, list):
            raise TypeError('Please use `List[Any]` instead of general sequence type like `list`.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, list):
            raise TypeError(f'Expect a list, found {type(plain)}: {plain}')
        result = []
        for i, value in enumerate(plain):
            with ctx.onto(i):
                result.append(TypeDef.load(self.inner_type, value, ctx=ctx))
        ctx.mark_cli_anchor_point(list)
        return result

    def to_plain(self, obj, ctx):
        if not isinstance(obj, list):
            raise TypeError(f'Expect a list, found {type(obj)}: {obj}')
        result = []
        for i, value in enumerate(obj):
            with ctx.onto(i):
                result.append(TypeDef.dump(self.inner_type, value, ctx=ctx))
        return result


class TupleDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) in (tuple, Tuple):
            self = cls(type_)
            # e.g., Tuple[int, str, float]
            self.inner_types = type_.__args__
            return self
        elif inspect.isclass(type_) and issubclass(type_, tuple):
            raise TypeError('Please use `Tuple[xxx]` instead of tuple.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, (list, tuple)):
            raise TypeError(f'Expect a list or a tuple, found {type(plain)}: {plain}')
        result = []
        for i, (type_, value) in enumerate(zip(self.inner_types, plain)):
            with ctx.onto(i):
                result.append(TypeDef.load(type_, value, ctx=ctx))
        ctx.mark_cli_anchor_point(list)
        return tuple(result)

    def to_plain(self, obj, ctx):
        if not isinstance(obj, tuple):
            raise TypeError(f'Expect a tuple, found {type(obj)}: {obj}')
        result = []
        for i, (type_, value) in enumerate(zip(self.inner_types, obj)):
            with ctx.onto(i):
                result.append(TypeDef.dump(type_, value, ctx=ctx))
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
        elif inspect.isclass(type_) and issubclass(type_, dict):
            raise TypeError('Please use `Dict[xxx, xxx]` instead of dict.')
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, dict):
            raise TypeError(f'Expect a dict, found {type(plain)}: {plain}')
        result = {}
        for key, value in plain.items():
            with ctx.onto(f'(key){key}'):
                key = TypeDef.load(self.key_type, key, ctx=ctx)
            with ctx.onto(str(key)):
                value = TypeDef.load(self.value_type, value, ctx=ctx)
            result[key] = value
        ctx.mark_cli_anchor_point(dict)
        return result

    def to_plain(self, obj, ctx):
        if not isinstance(obj, dict):
            raise TypeError(f'Expect a dict, found {type(obj)}: {obj}')
        result = {}
        for key, value in obj.items():
            with ctx.onto(f'(key){key}'):
                key = TypeDef.dump(self.key_type, key, ctx=ctx)
            with ctx.onto(str(key)):
                value = TypeDef.dump(self.value_type, value, ctx=ctx)
            result[key] = value
        return result


class EnumDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if inspect.isclass(type_) and issubclass(type_, Enum):
            return cls(type_)
        return None

    def from_plain(self, plain, ctx):
        result = self.type(plain)
        ctx.mark_cli_anchor_point(self.type)
        return result

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.type):
            raise TypeError(f'Expect a enum ({self.type}), found {obj}')
        return obj.value


class UnionDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) == Union:
            self = cls(type_)
            self.inner_types = list(type_.__args__)
            return self
        return None

    def from_plain(self, plain, ctx):
        # try types in union one by one, skip when validation error
        # until exhausted
        def _try_types(types):
            if not types:
                raise TypeError(f'All possible types from union {self.inner_types} are exhausted.')
            with ctx.match('union:' + getattr(types[0], '__name__', str(types[0]))):
                try:
                    return TypeDef.load(types[0], plain, ctx=ctx)
                    # catch both validation error and unsupported type error
                except (TypeError, ValidationError):
                    return _try_types(types[1:])

        return _try_types(self.inner_types)

    def to_plain(self, obj, ctx):
        def _try_types(types):
            if not types:
                raise TypeError(f'All possible types from union {self.inner_types} are exhausted.')
            with ctx.match('union:' + getattr(types[0], '__name__', str(types[0]))):
                try:
                    return TypeDef.dump(types[0], obj, ctx=ctx)
                except (TypeError, ValidationError):
                    return _try_types(types[1:])

        return _try_types(self.inner_types)


class PrimitiveDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if inspect.isclass(type_) and issubclass(type_, primitive_types):
            return cls(type_)
        return None

    def from_plain(self, plain, ctx):
        # support implicit conversion here
        if not isinstance(plain, primitive_types):
            raise ValueError(f'Cannot implicitly cast a variable with type {type(plain)}'
                             f' to {primitive_types}: {plain}')
        if issubclass(self.type, float):
            result = float(plain)
        elif issubclass(self.type, (int, bool)):
            # check converting to int is not numerically equal
            # to avoid mistakenly converting float to int
            if isinstance(plain, float) and int(plain) != plain:
                raise ValueError(f'Cannot implicitly cast float {plain} to int or bool')
            result = self.type(plain)
        else:
            result = self.type(plain)
        ctx.mark_cli_anchor_point(self.type)
        return result

    def to_plain(self, obj, ctx):
        if not isinstance(obj, self.type):
            raise TypeError(f'Expected {self.type}, found {obj} of type: {type(obj)}')
        return obj


class DataclassDef(TypeDef):
    @classmethod
    def new(cls, type_):
        if dataclasses.is_dataclass(type_):
            self = cls(type_)
            return self
        return None

    @staticmethod
    def _is_missing(obj: Any) -> bool:
        # no default value
        return isinstance(obj, type(dataclasses.MISSING))

    def validate(self, converted, ctx):
        for field in dataclasses.fields(converted):
            value = getattr(converted, field.name)
            typeguard.check_type(f'{value} ({ctx.current_name} -> {field.name})',
                                 value, field.type)

        # if dataclass has a post validation
        if hasattr(converted, 'post_validate'):
            try:
                result = converted.post_validate()
            except Exception as e:
                raise ValueError(f'{ctx.current_name}: validation failed. {repr(e)}')
            if isinstance(result, bool):
                if not result:
                    raise ValueError(f'{ctx.current_name}: post validation failed')
            else:
                ok, message = result
                if not ok:
                    raise ValueError(f'{ctx.current_name}: post validation failed with: {message}')

    def from_plain(self, plain, ctx, type_=None):
        if type_ is None:
            type_ = self.type
        if not isinstance(plain, dict) and not dataclasses.is_dataclass(plain):
            raise TypeError(f'Expect a dict or dataclass, but found {type(plain)}: {plain}')

        if dataclasses.is_dataclass(plain):
            # already done, no further creation is needed
            # only transform the inner fields here
            # NOTE: the transform is done "in-place"
            if not isinstance(plain, type_):
                raise TypeError(f'Expect a dataclass of type {type_}, but found {type(plain)}: {plain}')

            for field in dataclasses.fields(type_):
                with ctx.onto(field.name):
                    # retrieve & transform & update
                    value = getattr(plain, field.name)
                    value = TypeDef.load(field.type, value, ctx=ctx)
                    setattr(plain, field.name, value)

            inst = plain

        else:
            # copy the raw object to prevent unexpected modification
            plain = copy.copy(plain)

            # the content with name `_meta` is ignored
            # it is reserved for writing comments
            _meta = plain.pop('_meta', None)
            kwargs = {}
            for field in dataclasses.fields(type_):
                # get the values with content, otherwise default
                value = plain.pop(field.name, field.default)
                # if no default value exists
                if self._is_missing(value):
                    # throw error early
                    raise ValueError(f'`{field}` is expected, but it is not set')
                # Load should be done for both situations:
                # 1. value is set
                # 2. no value set, default value is used
                # Case 2 is to handle situations where users use plain format to write a default value
                with ctx.onto(field.name):
                    value = TypeDef.load(field.type, value, ctx=ctx)
                kwargs[field.name] = value
            if plain:
                fields = ', '.join(plain.keys())
                raise ValueError(f'{type_.__name__}: Unrecognized fields {fields}')

            # creating dataclass
            inst = type_(**kwargs)
            inst._meta = _meta

        ctx.mark_cli_anchor_point(dict)
        return inst

    def to_plain(self, obj, ctx, type_=None, result=None):
        if type_ is None:
            type_ = self.type
            # if type is dynamically generated, it won't pass check
            # so this check lives in if-branch
            if not isinstance(obj, type_):
                raise TypeError(f'Expected {type_}, found {obj} of type: {type(obj)}')
        if not result:
            result = {}
        for field in dataclasses.fields(obj):
            with ctx.onto(field.name):
                value = getattr(obj, field.name)
                result[field.name] = TypeDef.dump(field.type, value, ctx=ctx)
        return result


class ClassConfigDef(DataclassDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) == ClassConfig:
            # e.g., ClassConfig[nn.Conv2d]
            self = cls(type_)
            self.inner_type = dataclass_from_class(type_.__args__[0])
            return self
        return None

    def from_plain(self, plain, ctx):
        return super().from_plain(plain, ctx, type_=self.inner_type)

    def to_plain(self, obj, ctx):
        if not dataclasses.is_dataclass(obj) or not hasattr(obj, 'type') or self.inner_type._type != obj.type():
            raise TypeError(f'Expect a dataclass with type() equals {self.inner_type._type}, found {obj} of type {type(obj)}')
        return super().to_plain(obj, ctx, type_=self.inner_type)


class RegistryConfigDef(DataclassDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) == RegistryConfig:
            # e.g., ClassConfig[BACKBONES]
            self = cls(type_)
            # inner type is not available here
            self.registry = self.type.__args__[0]
            return self
        return None

    def from_plain(self, plain, ctx):
        if not isinstance(plain, dict) and 'type' in plain:
            raise TypeError(f'Expect a dict with key "type", but found {type(plain)}: {plain}')
        # copy the raw object to prevent unexpected modification
        plain = copy.copy(plain)
        type_, inherit = self.registry.get_module_with_inherit(plain.pop('type'))
        dataclass = dataclass_from_class(type_, inherit_signature=inherit)
        return super().from_plain(plain, ctx, type_=dataclass)

    def to_plain(self, obj, ctx):
        if not dataclasses.is_dataclass(obj) or not hasattr(obj, 'type'):
            raise TypeError(f'Expect a dataclass with type(), found {obj} of type {type(obj)}')
        # obj is a dataclass, type() is its original class
        type_name = self.registry.inverse_get(obj.type())
        return super().to_plain(obj, ctx, type_=obj.type(), result={'type': type_name})


class SubclassConfigDef(DataclassDef):
    @classmethod
    def new(cls, type_):
        if getattr(type_, '__origin__', None) == SubclassConfig:
            # e.g., SubclassConfig[nn.Module]
            self = cls(type_)
            # inner type is not available here
            self.base_class = self.type.__args__[0]
            return self
        return None

    @staticmethod
    def _find_class(cls_name: str, base_class: Type) -> Type:
        """Find class with exact class name or attribute named ``alias``.
        """
        def _iterate_subclass(base_class: Type) -> Iterable[Type]:
            for subclass in base_class.__subclasses__():
                yield subclass
                yield from _iterate_subclass(subclass)

        for subclass in _iterate_subclass(base_class):
            if subclass.__name__ == cls_name:
                return subclass
            if hasattr(subclass, 'alias') and subclass.alias == cls_name:
                return subclass
        if '.' in cls_name:
            path, identifier = cls_name.rsplit('.', 1)
            module = __import__(path, globals(), locals(), [identifier])
            if hasattr(module, identifier):
                subclass = getattr(module, identifier)
                assert issubclass(subclass, base_class), f'{subclass} is not a subclass of {base_class}.'
                return subclass
        raise ImportError(f"{cls_name} is not found in {base_class}'s subclasses and cannot be directly imported.")

    def from_plain(self, plain, ctx):
        if not isinstance(plain, dict) and 'type' in plain:
            raise TypeError(f'Expect a dict with key "type", but found {type(plain)}: {plain}')
        # copy the raw object to prevent unexpected modification
        plain = copy.copy(plain)

        type_ = self._find_class(plain.pop('type'), self.base_class)
        dataclass = dataclass_from_class(type_)
        return super().from_plain(plain, ctx, type_=dataclass)

    def to_plain(self, obj, ctx):
        if not dataclasses.is_dataclass(obj) or not hasattr(obj, 'type'):
            raise TypeError(f'Expect a dataclass with type(), found {obj} of type {type(obj)}')

        # obj is a dataclass, type() is its original class
        class_type = obj.type()

        # do the inverse of find class
        if hasattr(class_type, 'alias'):
            import_path = class_type.alias
        else:
            import_path = class_type.__module__ + '.' + class_type.__name__
            if self._find_class(import_path, self.base_class) != class_type:
                raise ImportError(f'{class_type} cannot be created via importing from {import_path}')

        return super().to_plain(obj, ctx, type_=class_type, result={'type': import_path})


# register all the modules in this file
TypeDefRegistry.register_module(module=AnyDef)
TypeDefRegistry.register_module(module=NoneTypeDef)
TypeDefRegistry.register_module(module=OptionalDef)
TypeDefRegistry.register_module(module=PathDef)
TypeDefRegistry.register_module(module=ListDef)
TypeDefRegistry.register_module(module=TupleDef)
TypeDefRegistry.register_module(module=DictDef)
TypeDefRegistry.register_module(module=EnumDef)
TypeDefRegistry.register_module(module=UnionDef)
TypeDefRegistry.register_module(module=PrimitiveDef)
TypeDefRegistry.register_module(module=DataclassDef)
TypeDefRegistry.register_module(module=ClassConfigDef)
TypeDefRegistry.register_module(module=RegistryConfigDef)
TypeDefRegistry.register_module(module=SubclassConfigDef)

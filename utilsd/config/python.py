"""
Python parser and validator of configs.

The first part of this file defines `PythonConfig`, which I recommend all config classes should inherit.
The second part of this file defines how `PythonConfig` can be written in yaml and command line arguments.
"""

import dataclasses
import inspect
import json
import os
import warnings
from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, TypeVar, Tuple, Union, Type, Generic, ClassVar, Iterator, Optional, List

from ..fileio.config import Config
from .exception import ValidationError
from .registry import Registry

T = TypeVar('T')


class ClassConfig(Generic[T]):
    pass


class RegistryConfig(Generic[T]):
    pass


class SubclassConfig(Generic[T]):
    pass


__all__ = ['PythonConfig', 'ClassConfig', 'RegistryConfig']


def _is_missing(obj: Any) -> bool:
    return isinstance(obj, type(dataclasses.MISSING))


def _strip_optional(type_hint):
    if str(type_hint).startswith('typing.Optional['):
        return _strip_optional(type_hint.__args__[0])
    if str(type_hint).startswith('typing.Union[') and type_hint.__args__[1] == type(None):
        return _strip_optional(type_hint.__args__[0])
    return type_hint


def _strip_import_path(type_name):
    return type_name.replace('typing.', '').replace('utilsd.config.python.', '')


def _is_path_like(type_hint):
    return _strip_optional(type_hint) in (Path, PosixPath, os.PathLike)


def _is_tuple(type_hint):
    return str(type_hint).startswith('Tuple')


def _iterate_subclass(base_class: Type) -> Iterator[Type]:
    for subclass in base_class.__subclasses__():
        yield subclass
        yield from _iterate_subclass(subclass)


def _find_class(cls_name: str, base_class: Type) -> Type:
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
    raise ValueError(f"{cls_name} is not found in {base_class}'s subclasses and cannot be directly imported.")


def _recognize_class_from_class_config(cls, value, pop=True):
    changed = False
    type_name = _strip_import_path(str(cls))
    if type_name.startswith('RegistryConfig['):
        registry = cls.__args__[0]
        assert isinstance(registry, Registry), 'Type in RegisterConfig should be a registry.'
        assert 'type' in value, f'Value must be a dict and should have "type". {value}'
        assert value['type'] in registry, f'Registry {registry} does not have {value["type"]}.'
        cls = PythonConfig.from_type(registry.get(value['type']))
        changed = True
    elif type_name.startswith('ClassConfig['):
        cls = PythonConfig.from_type(cls.__args__[0])
        changed = True
    elif type_name.startswith('SubclassConfig['):
        assert 'type' in value, f'Value must be a dict and should have "type". {value}'
        cls = PythonConfig.from_type(_find_class(value['type'], cls.__args__[0]))
        changed = True
    if changed and pop:  # figured this is a class config. Type is no longer needed.
        value.pop('type', None)
    return cls


def _is_type(value, type_hint) -> bool:
    # used in validation, to check whether value is of `type_hint`
    type_name = _strip_import_path(str(type_hint))
    if type_name.startswith('RegistryConfig[') or \
            type_name.startswith('ClassConfig[') or \
            type_name.startswith('SubclassConfig['):
        return dataclasses.is_dataclass(value)
    if type_name == 'Any':
        return True
    if type_name.startswith('Union['):
        return any([_is_type(value, arg) for arg in type_hint.__args__])
    if _is_path_like(type_hint):
        return _is_path_like(type(value)) or isinstance(value, str)
    if value is None:
        return type_name.startswith('Optional[') or type_hint == type(None)
    if type_name.startswith('List['):
        if not isinstance(value, list):
            return False
        return all([_is_type(v, type_hint.__args__[0]) for v in value])
    if type_name.startswith('Tuple['):
        if not isinstance(value, tuple) and not isinstance(value, list):
            return False
        return all([_is_type(v, arg) for v, arg in zip(value, type_hint.__args__)])
    if type_name.startswith('Dict['):
        if not isinstance(value, dict):
            return False
        return all([_is_type(k, type_hint.__args__[0]) and _is_type(v, type_hint.__args__[1]) for k, v in value.items()])
    try:
        return isinstance(value, type_hint)
    except TypeError:
        # unsupported types like Callable[[], ...]
        return False


def _construct_with_type(value, type_hint) -> Any:
    # used in construction: to convert value guided by `type_hint`.
    # this does not guarantee success. Needs an extra validation to make sure.
    if value is None:
        return value
    cls = _strip_optional(type_hint)
    type_name = _strip_import_path(str(cls))
    # relative paths loaded from config file are not relative to pwd
    if _is_path_like(cls):
        value = Path(value)
    # convert to tuple, list, dict if needed
    if type_name.startswith('List['):
        value = [_construct_with_type(v, cls.__args__[0]) for v in value]
    if type_name.startswith('Tuple['):
        value = tuple([_construct_with_type(v, arg) for v, arg in zip(value, cls.__args__)])
    if type_name.startswith('Dict['):
        value = {_construct_with_type(k, cls.__args__[0]): _construct_with_type(v, cls.__args__[1]) for k, v in value.items()}
    if type_name.startswith('Union['):
        exceptions = []
        for sub_type_name in type_hint.__args__:
            try:
                return _construct_with_type(value, sub_type_name)
            except Exception as e:
                exceptions.append(e)
        raise ValidationError(';  '.join([str(e) for e in exceptions]))

    # deal with primitive types:
    # in json, it's impossible to write float and int as key of dict;
    # in yaml, sometimes value will be incorrectly parsed (float as int or str)
    if cls == float:
        value = float(value)
    if cls == int:
        value = int(value)
    if cls == str:
        assert isinstance(value, (int, float, str))

    # convert to enum if needed
    if isinstance(cls, type) and issubclass(cls, Enum):
        value = cls(value)
    # convert nested dict to config type
    if isinstance(value, dict):
        cls = _recognize_class_from_class_config(cls, value)
        if isinstance(cls, type) and issubclass(cls, PythonConfig):
            value = cls(**value)
        elif not type_name.startswith('Dict['):
            raise TypeError(f"'{cls}' is not a config class.")
    return value


class PythonConfig:
    """
    This is modified from NNI's code.

    Base class of config classes.
    Subclass may override `_canonical_rules` and `_validation_rules`,
    `post_validate()` if extra validation is needed (global validation),
    and `validate()` if the logic is too complex to handle.
    """

    # Rules to validate field value.
    # The key is field name.
    # The value is callable `value -> valid` or `value -> (valid, error_message)`
    # The rule will be called with canonical format and is only called when `value` is not None.
    # `error_message` is used when `valid` is False.
    # It will be prepended with class name and field name in exception message.
    _validation_rules = {}  # type: ignore

    # Set true and the path will be enforced to exist.
    _check_path = True

    def __init__(self, **kwargs):
        """
        For subclasses, annotation should be @dataclass(init=False) due to the existence of this init function.
        Initialize a config object and set some fields. Nested config objects will be initialized.
        If a field is missing and don't have default value, it will be set to `dataclasses.MISSING`.
        """
        self._meta = kwargs.pop('_meta', None)
        class_name = type(self).__name__
        for field in dataclasses.fields(self):
            value = kwargs.pop(field.name, field.default)
            if value is not None and not _is_missing(value):
                try:
                    value = _construct_with_type(value, field.type)
                except Exception as e:
                    raise ValidationError(f'{class_name}: {field.name} construction error. {repr(e)}')
            setattr(self, field.name, value)
        if kwargs:
            cls = type(self).__name__
            fields = ', '.join(kwargs.keys())
            raise ValidationError(f'{cls}: Unrecognized fields {fields}')
        self.validate()

    def asdict(self) -> Dict[str, Any]:
        """
        Convert config to JSON object.
        """
        return dataclasses.asdict(self)

    def meta(self) -> dict:
        """
        Export meta.
        """
        return self._meta

    def check_path(self, path) -> bool:
        return not self._check_path or path.exists()

    def validate(self) -> None:
        """
        Validate the config object and raise Exception if it's ill-formed.
        """
        class_name = type(self).__name__
        config = self

        for field in dataclasses.fields(config):
            key, value = field.name, getattr(config, field.name)

            # check existence
            if _is_missing(value):
                raise ValidationError(f'{class_name}: {key} is not set')

            # check type annotation
            if field.type in [list, set, tuple, dict]:
                raise ValidationError(f'{class_name}: {field.type} cannot be list, set, tuple or dict. Please use XXX[Any] instead.')

            # check type
            if not _is_type(value, field.type):
                raise ValidationError(f'{class_name}: {value} failed to pass type check of {field.type}')

            # check path
            if isinstance(value, Path):
                assert self.check_path(value), f'Path {value} does not exist.'

            # check value range
            rule = config._validation_rules.get(key)
            if rule is not None:
                try:
                    result = rule(value)
                except Exception:
                    raise ValidationError(f'{class_name}: {key} has bad value {repr(value)}')

                if isinstance(result, bool):
                    if not result:
                        raise ValidationError(f'{class_name}: {key} ({repr(value)}) is out of range')
                else:
                    ok, message = result
                    if not ok:
                        raise ValidationError(f'{class_name}: {key} {message}')

            # check nested config
            if isinstance(value, PythonConfig):
                value.validate()

        # post validation check
        try:
            result = self.post_validate()
        except Exception as e:
            raise ValidationError(f'{class_name}: validation failed. {repr(e)}')
        if isinstance(result, bool):
            if not result:
                raise ValidationError(f'{class_name}: post validation failed')
        else:
            ok, message = result
            if not ok:
                raise ValidationError(f'{class_name}: post validation failed with: {message}')

    def post_validate(self) -> Union[bool, Tuple[bool, str]]:
        return True

    @classmethod
    def fromfile(cls: T, filename: str, **kwargs) -> T:
        config = Config.fromfile(filename, **kwargs)
        return cls(**config)

    @classmethod
    def fromcli(cls: T, *,
                shortcuts: Optional[Dict[str, str]] = None,
                allow_rest: bool = False,
                receive_nni: bool = False,
                respect_config: bool = True) -> Union[T, Tuple[T, List[str]]]:
        """Parse command line from a mandatory config file and optional arguments, like

            python main.py exp.yaml --learning_rate 1e-4

        Args:
            shortcuts (Optional[Dict[str, str]], optional): To create short command line arguments.
                In the form of ``{'-lr': 'trainer.learning_rate'}``. Defaults to None.
            allow_rest (bool, optional): If false, check if there is any unrecognized
                command line arguments. If false, ignore them. Defaults to False.
            receive_nni (bool, optional): Receive next parameters from NNI. Defaults to False.
            respect_config (bool, optional): Will try to read the config file first and get information
                like types to build a more comprehensive command line parser. Defaults to True.

        Raises:
            ValidationError: Config file is invalid.

        Returns:
            Union[PythonConfig, Tuple[PythonConfig, List[str]]]:
                If ``allow_rest``, a tuple of parsed config and the rest of command line arguments will be returned.
                Otherwise, the parse config only.
        """
        parser = ArgumentParser(add_help=False)
        parser.add_argument('exp', help='Experiment YAML file')
        args, _ = parser.parse_known_args()
        default_config = Config.fromfile(args.exp)

        if shortcuts is None:
            shortcuts = {}

        # gather overriding params from command line
        cls._build_command_line_parser(parser, shortcuts, default_config if respect_config else {})
        parser.add_argument(
            '-h', '--help', action='help', default=SUPPRESS,
            help='Show this help message and exit')
        args, rest = parser.parse_known_args()
        override_params = vars(args)
        override_params.pop('exp')
        default_config.merge_from_dict(override_params)

        if receive_nni:
            # gather params from nni
            import nni
            nni_params = nni.get_next_parameter() or {}
            default_config.merge_from_dict(nni_params)

        configs = cls(**default_config)

        if not allow_rest:
            if rest:
                raise ValidationError(f'Unexpected command line arguments: {rest}')
            return configs
        else:
            return configs, rest

    @classmethod
    def _build_command_line_parser(cls, parser, shortcuts, default_config, prefix=''):
        def str2bool(v):
            if isinstance(v, bool):
                return v
            if v.lower() in ('yes', 'true', 't', 'y', '1'):
                return True
            elif v.lower() in ('no', 'false', 'f', 'n', '0'):
                return False
            else:
                raise ArgumentTypeError('Boolean value expected.')

        def str2obj(v):
            lst = json.loads(v)
            return lst

        def infer_type(t):
            t = _strip_optional(t)
            if t in (int, float, str):
                return t
            if t == Path:
                return str
            if t == bool:
                return str2bool
            return str2obj

        assert issubclass(cls, PythonConfig), f'Interface class {cls} must be a subclass of `PythonConfig`.'

        names = []
        for field in fields(cls):
            field_type = _strip_optional(field.type)
            field_type_name = _strip_import_path(str(field_type))
            if is_dataclass(field_type):
                assert issubclass(field_type, PythonConfig), f'Interface class {field_type} must be a subclass of `PythonConfig`.'
                names += field_type._build_command_line_parser(parser, shortcuts, default_config.get(field.name, {}),
                                                               prefix=prefix + field.name + '.')
            elif any(field_type_name.startswith(config_type + '[')
                     for config_type in ['ClassConfig', 'RegistryConfig', 'SubclassConfig']):
                field_type_guess = _recognize_class_from_class_config(field.type, default_config.get(field.name, {}), pop=False)
                if is_dataclass(field_type_guess):
                    names += field_type_guess._build_command_line_parser(parser, shortcuts, default_config.get(field.name, {}),
                                                                         prefix=prefix + field.name + '.')
                elif field.name in default_config:
                    assert isinstance(default_config[field.name], dict), f'Expected {default_config[field.name]} to be a dict.'
                    for key, value in default_config[field.name].items():
                        name = prefix + field.name + '.' + key
                        # TODO: duplicated logic, needs to be refactored
                        names.append(name)
                        shortcut = shortcuts.get(name, [])
                        inferred_type = infer_type(type(value))
                        if inferred_type == str2bool:
                            parser.add_argument('--' + name, type=inferred_type, default=SUPPRESS)
                            if shortcut:
                                parser.add_argument(*shortcut, action='store_true', dest=name)
                        else:
                            parser.add_argument('--' + name, *shortcut, type=inferred_type, default=SUPPRESS)
            else:
                name = prefix + field.name
                names.append(name)
                shortcut = shortcuts.get(name, [])
                if inspect.isclass(field_type) and issubclass(field_type, Enum):
                    parser.add_argument('--' + name, *shortcut, dest=name, type=str,
                                        default=SUPPRESS, choices=[e.value for e in field_type])
                else:
                    inferred_type = infer_type(field_type)
                    if inferred_type == str2bool:
                        parser.add_argument('--' + name, type=inferred_type, default=SUPPRESS)
                        if shortcut:
                            parser.add_argument(*shortcut, action='store_true', dest=name)
                    else:
                        parser.add_argument('--' + name, *shortcut, type=inferred_type, default=SUPPRESS)
        return names

    @classmethod
    def from_type(cls: T, t: Type) -> T:
        class_name = t.__name__ + 'Config'
        init_signature = inspect.signature(t.__init__)
        fields = [
            ('_type', ClassVar[Type], t),
        ]
        for param in init_signature.parameters.values():
            if param.name == 'self':
                continue
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # TODO: fix type annotation for dependency injection
            assert param.annotation != param.empty, f'Parameter must have annotation: {param}'
            if param.default != param.empty:
                fields.append((param.name, param.annotation, param.default))
            else:
                fields.append((param.name, param.annotation))

        def type_fn(self): return self._type

        def build_fn(self, **kwargs):
            result = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
            for k in kwargs:
                # silently overwrite the arguments with given ones.
                result[k] = kwargs[k]
            try:
                return self._type(**result)
            except:
                warnings.warn(f'Error when constructing {self._type} with {result}.', RuntimeWarning)
                raise

        return dataclasses.make_dataclass(class_name, fields, bases=(cls,), init=False,
                                          namespace={'type': type_fn, 'build': build_fn})

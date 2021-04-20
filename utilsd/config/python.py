"""
Python parser and validator of configs.

The first part of this file defines `PythonConfig`, which I recommend all config classes should inherit.
The second part of this file defines how `PythonConfig` can be written in yaml and command line arguments.
"""

import dataclasses
import inspect
import json
import os
from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, TypeVar, Tuple, Union

from mmcv.utils import Config

T = TypeVar('T', bound='PythonConfig')

__all__ = ['PythonConfig']


def _is_missing(obj: Any) -> bool:
    return isinstance(obj, type(dataclasses.MISSING))


def _strip_optional(type_hint):
    if str(type_hint).startswith('typing.Optional['):
        return _strip_optional(type_hint.__args__[0])
    if str(type_hint).startswith('typing.Union[') and type_hint.__args__[1] == type(None):
        return _strip_optional(type_hint.__args__[0])
    return type_hint


def _is_path_like(type_hint):
    return _strip_optional(type_hint) == Path or _strip_optional(type_hint) == os.PathLike


def _is_tuple(type_hint):
    return str(type_hint).startswith('Tuple')


def _is_type(value, type_hint) -> bool:
    # used in validation, to check whether value is of `type_hint`
    type_name = str(type_hint).replace('typing.', '')
    if type_name == 'Any':
        return True
    if type_name.startswith('Union['):
        return any([_is_type(value, arg) for arg in type_hint.__args__])
    if value is None:
        return type_name.startswith('Optional[') or type_hint == type(None)
    if type_name.startswith('List['):
        if not isinstance(value, list):
            return False
        return all([_is_type(v, type_hint.__args__[0]) for v in value])
    if type_name.startswith('Tuple['):
        if not isinstance(value, tuple):
            return False
        return all([_is_type(v, arg) for v, arg in zip(value, type_hint.__args__)])
    if type_name.startswith('Dict['):
        if not isinstance(value, dict):
            return False
        return all([_is_type(k, type_hint.__args__[0]) and _is_type(v, type_hint.__args__[1]) for k, v in value.items()])
    return isinstance(value, type_hint)


def _construct_with_type(value, type_hint) -> Any:
    # used in construction: to convert value guided by `type_hint`.
    # this does not guarantee success. Needs an extra validation to make sure.
    if value is None:
        return value
    cls = _strip_optional(type_hint)
    type_name = str(cls).replace('typing.', '')
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

    # deal with primitive types:
    # in json, it's impossible to write float and int as key of dict;
    # in yaml, sometimes value will be incorrectly parsed (float as int or str)
    if cls == float:
        value = float(value)
    if cls == int:
        value = int(value)

    # convert to enum if needed
    if isinstance(cls, type) and issubclass(cls, Enum):
        value = cls(value)
    # convert nested dict to config type
    if isinstance(value, dict):
        if isinstance(cls, type) and issubclass(cls, PythonConfig):
            value = cls(**value)
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
                    raise ValueError(f'{class_name}: {field.name} construction error. {repr(e)}')
            setattr(self, field.name, value)
        if kwargs:
            cls = type(self).__name__
            fields = ', '.join(kwargs.keys())
            raise ValueError(f'{cls}: Unrecognized fields {fields}')
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
                raise ValueError(f'{class_name}: {key} is not set')

            # check type annotation
            if field.type in [list, set, tuple, dict]:
                raise ValueError(f'{class_name}: {field.type} cannot be list, set, tuple or dict. Please use XXX[Any] instead.')

            # check type
            if not _is_type(value, field.type):
                raise ValueError(f'{class_name}: {value} failed to pass type check of {field.type}')

            # check path
            if self._check_path and isinstance(value, Path):
                assert value.exists(), f'Path {value} does not exist.'

            # check value range
            rule = config._validation_rules.get(key)
            if rule is not None:
                try:
                    result = rule(value)
                except Exception:
                    raise ValueError(f'{class_name}: {key} has bad value {repr(value)}')

                if isinstance(result, bool):
                    if not result:
                        raise ValueError(f'{class_name}: {key} ({repr(value)}) is out of range')
                else:
                    ok, message = result
                    if not ok:
                        raise ValueError(f'{class_name}: {key} {message}')

            # check nested config
            if isinstance(value, PythonConfig):
                value.validate()

        # post validation check
        try:
            result = self.post_validate()
        except Exception as e:
            raise ValueError(f'{class_name}: validation failed. {repr(e)}')
        if isinstance(result, bool):
            if not result:
                raise ValueError(f'{class_name}: post validation failed')
        else:
            ok, message = result
            if not ok:
                raise ValueError(f'{class_name}: post validation failed with: {message}')

    def post_validate(self) -> Union[bool, Tuple[bool, str]]:
        return True

    @classmethod
    def fromfile(cls, filename, **kwargs):
        config = Config.fromfile(filename, **kwargs)
        return cls(**config)

    @classmethod
    def fromcli(cls, shortcuts=None, allow_rest=False, receive_nni=False):
        """
        Parse command line from a mandatory config file and optional arguments, like

            python main.py exp.yaml --learning_rate 1e-4
        """
        parser = ArgumentParser(add_help=False)
        parser.add_argument('exp', help='Experiment YAML file')
        args, _ = parser.parse_known_args()
        default_config = Config.fromfile(args.exp)

        if shortcuts is None:
            shortcuts = {}

        # gather overriding params from command line
        cls._build_command_line_parser(parser, shortcuts)
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
                raise ValueError(f'Unexpected command line arguments: {rest}')
            return configs
        else:
            return configs, rest

    @classmethod
    def _build_command_line_parser(cls, parser, shortcuts, prefix=''):
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
            if t == bool:
                return str2bool
            return str2obj

        assert issubclass(cls, PythonConfig), f'Interface class {cls} must be a subclass of `PythonConfig`.'

        names = []
        for field in fields(cls):
            field_type = _strip_optional(field.type)
            if is_dataclass(field_type):
                assert issubclass(field_type, PythonConfig), f'Interface class {field_type} must be a subclass of `PythonConfig`.'
                names += field_type._build_command_line_parser(parser, shortcuts, prefix=prefix + field.name + '.')
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

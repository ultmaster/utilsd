"""
Interface of config classes.
The original PythonConfig is kept for compatibility purposes.
"""

import dataclasses
import inspect
import json
import os
import warnings
from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError
from dataclasses import fields, is_dataclass, dataclass
from enum import Enum
from pathlib import Path, PosixPath
from typing import Any, Dict, TypeVar, Tuple, Union, Type, Generic, ClassVar, Iterator, Protocol, Optional, List

from ..fileio.config import Config
from .exception import ValidationError
from .registry import Registry
from .type_def import ParseContext, TypeDef

T = TypeVar('T')


class BaseConfig(Protocol):
    """Interface for config
    """

    def asdict(self) -> Dict[str, Any]:
        """Convert config to JSON object."""
        ...

    def meta(self) -> dict:
        """Export metadata."""
        ...

    @classmethod
    def fromfile(cls: T, filename: Path, **kwargs) -> T:
        """Create a config by reading from ``filename``.

        Args:
            filename (path): Path to read from
        """
        ...

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
        ...


def configclass(cls: T) -> Union[T, BaseConfig]:
    cls = dataclass(cls)

    def asdict(self):
        return TypeDef.dump(cls, self, ParseContext())

    def meta(self):
        return getattr(self, '_meta', {})

    @classmethod
    def fromfile(cls, filename, **kwargs):
        config = Config.fromfile(filename, **kwargs)
        return TypeDef.load(cls, config, ParseContext())

    @classmethod
    def fromcli(cls: T, *, shortcuts=None, allow_rest=False, receive_nni=False, respect_config=True):
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

    # add four methods to match protocol
    cls.asdict = asdict
    cls.meta = meta
    cls.fromfile = fromfile
    cls.fromcli = fromcli
    return cls


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

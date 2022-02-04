"""
Interface of config classes.
The original PythonConfig is kept for compatibility purposes.
"""

import warnings
from argparse import ArgumentParser, SUPPRESS
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, TypeVar, Tuple, Union, Optional, List

if True:  # prevent reordering by formatter
    try:
        from typing import Protocol
    except ImportError:
        from typing_extensions import Protocol

from ..fileio.config import Config
from .cli_parser import CliContext
from .exception import ValidationError
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
    def fromdict(cls: T, data: Any) -> T:
        """Create a config by parsing ``data``.

        Args:
            data (any): Data to parse. Should be a dict in most cases.
        """
        ...

    @classmethod
    def fromcli(cls: T, *,
                shortcuts: Optional[Dict[str, str]] = None,
                allow_rest: bool = False,
                receive_nni: bool = False) -> Union[T, Tuple[T, List[str]]]:
        """Parse command line from a mandatory config file and optional arguments, like

            python main.py exp.yaml --learning_rate 1e-4

        Args:
            shortcuts (Optional[Dict[str, str]], optional): To create short command line arguments.
                In the form of ``{'-lr': 'trainer.learning_rate'}``. Defaults to None.
            allow_rest (bool, optional): If false, check if there is any unrecognized
                command line arguments. If false, ignore them. Defaults to False.
            receive_nni (bool, optional): Receive next parameters from NNI. Defaults to False.

        Raises:
            ValidationError: Config file is invalid.

        Returns:
            Union[PythonConfig, Tuple[PythonConfig, List[str]]]:
                If ``allow_rest``, a tuple of parsed config and the rest of command line arguments will be returned.
                Otherwise, the parse config only.
        """
        ...


def configclass(cls: T) -> Union[T, BaseConfig]:
    """
    Make a class a config class.
    The class should be written like a `dataclass <https://docs.python.org/3/library/dataclasses.html>`__,
    and annotated with ``@configclass``. Then it can load content from YAML files or python dict.

    Returns:
        BaseConfig:
            The annotated config class.

    Examples:

        To create a config class: ::

            @configclass
            class UserConf:
                username: str
                password: str
                attempt: Optional[int] = None

        To load from a file or content: ::

            config = UserConf.fromfile('config.yml')
            config = UserConf.fromdict({'username': 'john', 'password': 123})

        To parse from commnad line: ::

            config = UserConf.fromcli()

        Then in command line, it accepts a file which is considered as "base config".
        The base config should be load-able with ``UserConf.fromfile``.
        Most of the fields in the config can be overridden with command line arguments. ::

            $ python test.py config.yml --username "grace"

        Use ``-h`` for help.

            $ python test.py config.yml -h

        It is essentially a dataclass, and thus all the methods that apply to dataclass similarly apply. ::

            UserConf('john', '123', attempt=0)
    """
    cls = dataclass(cls)

    # add four methods to match protocol
    cls.asdict = _asdict
    cls.meta = _meta
    cls.fromdict = _fromdict
    cls.fromfile = _fromfile
    cls.fromcli = _fromcli
    return cls


def _asdict(self):
    return TypeDef.dump(self.__class__, self)


def _meta(self):
    return getattr(self, '_meta', {})


@classmethod
def _fromfile(cls, filename, **kwargs):
    config = Config.fromfile(filename, **kwargs)
    return TypeDef.load(cls, config.asdict())


@classmethod
def _fromdict(cls, data):
    return TypeDef.load(cls, data)


@classmethod
def _fromcli(cls: T, *, shortcuts=None, allow_rest=False, receive_nni=False):
    if shortcuts is None:
        shortcuts = {}

    description = """Command line auto-generated with utilsd.config.
A path to base config file (like JSON/YAML) needs to be specified first.
Then some extra arguments to override the fields in the base config.
Please note the type of arguments (always use `-h` for reference):
`JSON` type means the field accepts a `JSON` for overriding.
    """

    parser = ArgumentParser(description=description, add_help=False)
    parser.add_argument('exp', help='Experiment YAML file')
    args, _ = parser.parse_known_args()
    default_config = Config.fromfile(args.exp)

    # TODO: default config actually can have missing fields
    cli_context = CliContext()

    # first-pass
    TypeDef.load(cls, default_config.asdict(), ParseContext(cli_context))

    cli_context.build_parser(parser, shortcuts)
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

    # second-pass
    configs = TypeDef.load(cls, default_config.asdict())

    if not allow_rest:
        if rest:
            raise ValidationError(f'Unexpected command line arguments: {rest}')
        return configs
    else:
        return configs, rest


class PythonConfig:
    """
    The original base class for config classes.
    Deprecated now.
    """

    def __init__(self):
        super().__init__()
        warnings.warn('PythonConfig is deprecated and will be removed in future releases. '
                      'Please use @configclass instead.', category=DeprecationWarning)

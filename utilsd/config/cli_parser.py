import json
from argparse import ArgumentParser, ArgumentTypeError, SUPPRESS
from enum import Enum
from typing import Dict, Type, List


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
    if issubclass(t, (int, float, str)):
        return t
    if issubclass(t, bool):
        return str2bool
    return str2obj


metavars = {
    int: 'INTEGER',
    str: 'STRING',
    float: 'FLOAT',
    bool: 'BOOL',
    list: 'JSON',
    dict: 'JSON'
}


class CliContext:
    """Hold context to create an argument parser."""

    def __init__(self):
        self.visited: Dict[str, Type] = {}

    def add_argument(self, name: str, type_: Type) -> None:
        # silently dedup. I'm not sure about side effects.
        if name in self.visited:
            return
        self.visited[name] = type_

    def build_parser(self, parser: ArgumentParser,
                     shortcuts: Dict[str, List[str]]) -> None:
        """Modify the parser so that it can handle the names in "visited"."""
        for name in sorted(self.visited.keys()):
            type_ = self.visited[name]
            shortcut = shortcuts.get(name, [])

            if not isinstance(shortcut, list):
                raise TypeError(f'Shortcut of {name} is not found to be a list: {shortcut}')

            if type_ is type(None):
                # ignore None type when building parser
                pass
            elif issubclass(type_, Enum):
                parser.add_argument('--' + name, *shortcut, dest=name, type=str, metavar='STRING',
                                    default=SUPPRESS, choices=[e.value for e in type_])
            elif type_ in (int, str, float, bool, list, dict):
                inferred_type = infer_type(type_)
                parser.add_argument('--' + name, *shortcut, metavar=metavars[type_],
                                    type=inferred_type, default=SUPPRESS)
            else:
                raise TypeError(f'Unsupported type to add argument: {type_}')

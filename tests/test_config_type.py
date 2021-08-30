import os
from typing import Union

import pathlib
import typing

from utilsd.config import PythonConfig, configclass
from utilsd.config.python import _is_path_like


def test_path():
    assert _is_path_like(pathlib.Path)
    assert _is_path_like(os.PathLike)
    assert not _is_path_like(typing.List[pathlib.Path])
    assert not _is_path_like(typing.Union[pathlib.Path, str])
    assert _is_path_like(typing.Optional[pathlib.Path])


def _test_type(T, value):
    @configclass
    class Main(PythonConfig):
        var: T

    return Main(var=value).var


def test_union():
    @configclass
    class Foo(PythonConfig):
        bar: int = 1

    assert _test_type(Union[pathlib.Path, Foo], '/bin').as_posix() == '/bin'
    assert _test_type(Union[pathlib.Path, Foo], {'bar': 2}).bar == 2
    assert _test_type(Union[str, typing.Tuple[str, str]], ['1', '2']) == ('1', '2')

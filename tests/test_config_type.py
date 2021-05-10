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


def test_union():
    @configclass
    class Foo(PythonConfig):
        bar: int = 1

    @configclass
    class Main(PythonConfig):
        foo: Union[pathlib.Path, Foo]

    assert Main(**{'foo': '/bin'}).foo.as_posix() == '/bin'
    assert Main(**{'foo': {'bar': 2}}).foo.bar == 2

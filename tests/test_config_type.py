import os

import pathlib
import typing

from utilsd.config.python import _is_path_like


def test_path():
    assert _is_path_like(pathlib.Path)
    assert _is_path_like(os.PathLike)
    assert not _is_path_like(typing.List[pathlib.Path])
    assert not _is_path_like(typing.Union[pathlib.Path, str])
    assert _is_path_like(typing.Optional[pathlib.Path])

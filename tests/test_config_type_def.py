import os
import pathlib
import typing
from dataclasses import dataclass
from enum import Enum

import pytest

from utilsd.config import ValidationError
from utilsd.config.type_def import TypeDef


def test_path():
    TypeDef.load(pathlib.Path, '/bin') == pathlib.Path('/bin')
    TypeDef.load(os.PathLike, '/bin') == pathlib.Path('/bin')
    TypeDef.load(pathlib.PosixPath, '/bin') == pathlib.Path('/bin')
    TypeDef.dump(pathlib.Path, pathlib.Path('/bin')) == '/bin'


def test_any():
    TypeDef.load(typing.Any, 123) == 123
    TypeDef.dump(typing.Any, '456') == '456'


def test_unsupported_type():
    with pytest.raises(TypeError) as e_info:
        TypeDef.load(typing.Callable[[], str], lambda x: x)
    assert 'Callable[[], str]' in str(e_info)


def test_primitive():
    res = TypeDef.load(int, 1.0)
    assert res == 1 and isinstance(res, int)
    with pytest.raises(ValidationError) as e_info:
        TypeDef.load(int, 1.5)
    assert 'implicit' in str(e_info)

    res = TypeDef.load(float, '123.45')
    assert res == 123.45

    assert TypeDef.load(bool, 42) == True

    with pytest.raises(ValidationError):
        TypeDef.dump(int, 123.45)

    assert TypeDef.dump(bool, False) == False
    assert TypeDef.dump(str, '123') == '123'

    # union int float
    assert TypeDef.load(typing.Union[int, float], 2.5) == 2.5
    assert TypeDef.load(typing.List[typing.Union[int, float]], [1, 2.5]) == [1, 2.5]


def test_list():
    assert TypeDef.load(typing.List[int], [1, 2, 3]) == [1, 2, 3]
    assert TypeDef.load(typing.List[float], ['1.0', 2.5, 3]) == [1., 2.5, 3.]
    assert TypeDef.load(typing.List[pathlib.Path], ['/bin', '/etc']) == \
        [pathlib.Path('/bin'), pathlib.Path('/etc')]
    assert TypeDef.load(typing.List[typing.List[int]], [[1, 2], [1, 2]]) == [[1, 2], [1, 2]]

    with pytest.raises(ValidationError) as e_info:
        TypeDef.load(typing.List[typing.List[int]], [1, 2])
    assert 'index:0' in str(e_info)

    assert TypeDef.dump(typing.List[typing.Tuple[str, str]], [('a', 'b'), ('a', 'c')]) == \
        [('a', 'b'), ('a', 'c')]


def test_tuple():
    assert TypeDef.load(typing.Tuple[int, int], [1, 2]) == (1, 2)
    assert TypeDef.load(typing.Tuple[int, str, float], ['1', 2, False]) == (1, '2', 0.)
    with pytest.raises(ValidationError) as e_info:
        TypeDef.load(typing.Tuple[int, ...], (1, 2))
    assert 'Ellipsis' in str(e_info)

    with pytest.raises(ValidationError):
        TypeDef.dump(typing.Tuple[str, str], ['abc', 'def'])
    TypeDef.dump(typing.Tuple[bool, ], (True,)) == (True, )


def test_dict():
    assert TypeDef.load(typing.Dict[str, int], {'a': 1, 'b': 2}) == {'a': 1, 'b': 2}
    with pytest.raises(ValidationError) as e_info:
        TypeDef.load(typing.Dict[str, int], [('a', 1), ('b', 2)])
    assert 'Expect a dict' in str(e_info)

    assert TypeDef.load(typing.Dict[str, typing.Dict[str, typing.Dict[str, str]]],
                        {'a': {'b': {'c': 'd'}}}) == {'a': {'b': {'c': 'd'}}}

    with pytest.raises(ValidationError) as e_info:
        TypeDef.load(typing.Dict[str, typing.Dict[str, typing.Dict[str, int]]],
                     {'a': {'b': {'c': 'd'}}})
    assert 'a -> b -> c' in str(e_info)


def test_enum():
    pass


def test_union():
    @dataclass
    class Foo:
        bar: int = 1

    assert _test_type(Union[pathlib.Path, Foo], '/bin') == pathlib.Path('/bin')
    assert _test_type(Union[pathlib.Path, Foo], {'bar': 2}).bar == 2
    assert _test_type(Union[str, typing.Tuple[str, str]], ['1', '2']) == ('1', '2')
    assert _test_type(Union[pathlib.Path, None], None) == None


class MyEnum(str, Enum):
    state1 = 'state1_val'
    state2 = 'state2_val'


test_path()
test_any()
test_unsupported_type()
test_primitive()
test_list()
test_tuple()
test_dict()

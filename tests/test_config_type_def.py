import os
import pathlib
import typing
from dataclasses import dataclass
from enum import Enum

import pytest

from utilsd.config import ClassConfig, ValidationError
from utilsd.config.type_def import TypeDef


def test_path():
    assert TypeDef.load(pathlib.Path, '/bin') == pathlib.Path('/bin')
    assert TypeDef.load(os.PathLike, '/bin') == pathlib.Path('/bin')
    assert TypeDef.load(pathlib.PosixPath, '/bin') == pathlib.Path('/bin')
    assert TypeDef.dump(pathlib.Path, pathlib.Path('/bin')) == '/bin'


def test_any():
    assert TypeDef.load(typing.Any, 123) == 123
    assert TypeDef.dump(typing.Any, '456') == '456'


def test_none():
    assert TypeDef.load(type(None), None) == None
    assert TypeDef.dump(type(None), None) == None

    with pytest.raises(ValidationError, match='must be NoneType'):
        TypeDef.load(type(None), 1)
    with pytest.raises(ValidationError, match='Expected None'):
        TypeDef.dump(type(None), "123")


def test_unsupported_type():
    with pytest.raises(TypeError, match=r'.*Callable\[\[\], str\].*'):
        TypeDef.load(typing.Callable[[], str], lambda x: x)

    with pytest.raises(TypeError, match=r'.*Callable\[\[\], str\].*'):
        TypeDef.dump(typing.Callable[[], str], lambda x: x)


def test_optional():
    assert TypeDef.load(typing.Optional[int], None) == None
    assert TypeDef.load(typing.Optional[int], 2) == 2
    with pytest.raises(ValidationError, match='optional -> primitive'):
        TypeDef.load(typing.Optional[int], 1.5)
    assert TypeDef.dump(typing.Optional[int], None) == None
    assert TypeDef.dump(typing.Optional[int], 2) == 2


def test_primitive():
    res = TypeDef.load(int, 1.0)
    assert res == 1 and isinstance(res, int)
    with pytest.raises(ValidationError, match='.*implicit.*'):
        TypeDef.load(int, 1.5)

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

    with pytest.raises(ValidationError, match='index:0'):
        TypeDef.load(typing.List[typing.List[int]], [1, 2])

    assert TypeDef.dump(typing.List[typing.Tuple[str, str]], [('a', 'b'), ('a', 'c')]) == \
        [('a', 'b'), ('a', 'c')]


def test_tuple():
    assert TypeDef.load(typing.Tuple[int, int], [1, 2]) == (1, 2)
    assert TypeDef.load(typing.Tuple[int, str, float], ['1', 2, False]) == (1, '2', 0.)
    with pytest.raises(ValidationError, match='Ellipsis'):
        TypeDef.load(typing.Tuple[int, ...], (1, 2))

    with pytest.raises(ValidationError):
        TypeDef.dump(typing.Tuple[str, str], ['abc', 'def'])
    TypeDef.dump(typing.Tuple[bool, ], (True,)) == (True, )


def test_dict():
    assert TypeDef.load(typing.Dict[str, int], {'a': 1, 'b': 2}) == {'a': 1, 'b': 2}
    with pytest.raises(ValidationError, match='Expect a dict'):
        TypeDef.load(typing.Dict[str, int], [('a', 1), ('b', 2)])

    assert TypeDef.load(typing.Dict[str, typing.Dict[str, typing.Dict[str, str]]],
                        {'a': {'b': {'c': 'd'}}}) == {'a': {'b': {'c': 'd'}}}

    with pytest.raises(ValidationError, match='a -> b -> c'):
        TypeDef.load(typing.Dict[str, typing.Dict[str, typing.Dict[str, int]]],
                     {'a': {'b': {'c': 'd'}}})

    with pytest.raises(ValidationError):
        TypeDef.dump(typing.Dict[str, int], {'abc': 123.0})
    with pytest.raises(ValidationError):
        # unsupported type
        TypeDef.dump(typing.Dict[str, int], {'abc', 123.0})
    assert TypeDef.dump(typing.Dict[str, int], {'abc': 123}) == {'abc': 123}


def test_enum():
    class MyEnum(str, Enum):
        state1 = 'state1_val'
        state2 = 'state2_val'

    assert TypeDef.load(MyEnum, 'state2_val') == MyEnum.state2
    assert TypeDef.dump(MyEnum, MyEnum.state1) == 'state1_val'
    with pytest.raises(ValidationError, match='is not a valid'):
        TypeDef.load(MyEnum, 'other')
    with pytest.raises(ValidationError, match='Expect a enum'):
        TypeDef.dump(MyEnum, 'state1_val')


def test_dataclass():
    @dataclass
    class Bar:
        n: int

    @dataclass
    class Foo:
        a: int
        b: float
        c: Bar

    assert Foo(a=1, b=2.0, c=Bar(n=0)).c.n == 0
    assert TypeDef.load(Foo, dict(a=1, b=2.0, c={'n': 0})).c.n == 0

    d = dict(a=1, b=2.0, c={'n': 0})
    TypeDef.load(Foo, d)
    assert len(d) == 3

    with pytest.raises(ValidationError, match='not set'):
        TypeDef.load(Foo, dict(a=1, c={'n': 0}))

    assert TypeDef.load(Foo, dict(a=1, b=2.0, c={'n': 0},
                                  _meta={'a': 42}))._meta == {'a': 42}
    assert TypeDef.load(Foo, Foo(a=1, b=2.0, c=Bar(n=0))).c.n == 0

    @dataclass
    class Bar:
        n: int = '2'

    @dataclass
    class Foo:
        a: int
        b: float
        c: Bar = Bar()

    assert Foo(a=1, b=2.0).c.n == '2'
    with pytest.raises(ValidationError, match='c -> n'):
        TypeDef.dump(Foo, Foo(a=1, b=2.0))
    assert TypeDef.load(Foo, dict(a=1, b=2.0)).c.n == 2
    # it can be dumped now because transform is in-place
    assert TypeDef.dump(Foo, Foo(a=1, b=2.0)) == {'a': 1, 'b': 2.0, 'c': {'n': 2}}

    @dataclass
    class Foo:
        a: int
        b: float

        def post_validate(self):
            return self.a == self.b

    with pytest.raises(ValidationError, match='validation failed'):
        TypeDef.load(Foo, dict(a=1, b=2.0))

    assert TypeDef.load(Foo, dict(a=1, b=1)).a == 1


def test_union():
    @dataclass
    class Foo:
        bar: int = 1

    assert TypeDef.load(typing.Union[pathlib.Path, Foo], '/bin') == pathlib.Path('/bin')
    assert TypeDef.load(typing.Union[pathlib.Path, Foo], {'bar': 2}).bar == 2
    assert TypeDef.load(typing.Union[str, typing.Tuple[str, str]], ['1', '2']) == ('1', '2')
    assert TypeDef.load(typing.Union[pathlib.Path, None], None) == None

    assert TypeDef.load(typing.Union[typing.List[int], typing.List[float]], [1, 2.5, '3']) == [1, 2.5, 3]
    with pytest.raises(ValidationError, match='are exhausted'):
        assert TypeDef.load(typing.Union[typing.List[int], typing.List[bool]], [1, 2.5, '3']) == [1, 2.5, 3]

    with pytest.raises(ValidationError, match='are exhausted'):
        TypeDef.dump(typing.Union[pathlib.Path, Foo], '/bin')
    assert TypeDef.dump(typing.Union[pathlib.Path, str], '/bar') == '/bar'
    assert TypeDef.dump(typing.Union[pathlib.Path, Foo], Foo(bar=2))['bar'] == 2
    assert TypeDef.dump(typing.Union[str, typing.Tuple[str, str]], ('1', '2')) == ('1', '2')
    assert TypeDef.dump(typing.Union[pathlib.Path, None], None) == None


def test_complex_optional_union():
    @dataclass
    class Foo:
        bar: int = 1

    assert TypeDef.load(typing.Optional[typing.Union[pathlib.Path, Foo]], '/bin') == pathlib.Path('/bin')
    assert TypeDef.load(typing.Optional[typing.Union[pathlib.Path, Foo]], {'bar': 2}).bar == 2
    assert TypeDef.load(typing.Optional[typing.Union[pathlib.Path, Foo]], None) == None

    assert TypeDef.load(typing.Union[pathlib.Path, Foo, type(None)], None) == None
    with pytest.raises(ValidationError, match='are exhausted'):
        TypeDef.load(typing.Union[pathlib.Path, Foo, type(None)], [1, 2.5, '3'])

    with pytest.raises(ValidationError, match='are exhausted'):
        TypeDef.dump(typing.Union[pathlib.Path, Foo, type(None)], "/bin")

    assert TypeDef.dump(typing.Optional[typing.Union[pathlib.Path, str]], '/bin') == '/bin'
    assert TypeDef.dump(typing.Optional[typing.Union[pathlib.Path, Foo]], Foo(bar=2))['bar'] == 2
    assert TypeDef.dump(typing.Optional[typing.Union[pathlib.Path, Foo]], None) == None

    assert TypeDef.dump(typing.Union[pathlib.Path, Foo, type(None)], None) == None


def test_class_config():
    class module:
        def __init__(self, a, b, c=1):
            pass

    with pytest.raises(TypeError, match='must have annotation'):
        TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2})

    class module:
        def __init__(self, a: int, b: int, c: int = 1):
            self._a = a
            self._b = b

    assert TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2}).a == 1
    assert TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2}).type() == module
    assert TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2}).build()._a == 1

    result = TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2})
    assert isinstance(result, ClassConfig)
    assert issubclass(type(result), ClassConfig)

    assert TypeDef.dump(ClassConfig[module], result) == {'a': 1, 'b': 2, 'c': 1}

    @dataclass
    class FakeDataclass:
        a: int = 1
        b: int = 2

    with pytest.raises(ValidationError, match='Expect a dataclass with type'):
        TypeDef.dump(ClassConfig[module], FakeDataclass())

    class module:
        def __init__(self, a: int, b: int, c: int = 1.5):
            self._a = a
            self._b = b

    with pytest.raises(ValidationError, match='implicit'):
        TypeDef.load(ClassConfig[module], {'a': 1, 'b': 2})

    class submodule:
        def __init__(self, a: int, b: int, c: int = 0):
            self._a = a
            self._b = b
            self._c = c

    class module:
        def __init__(self, a: submodule, b: submodule):
            pass

    with pytest.raises(ValidationError, match='No hook found'):
        TypeDef.load(ClassConfig[module], {'a': {'a': 1, 'b': 2}, 'b': {'a': 3, 'b': 4, 'c': 5}})

    class module:
        def __init__(self, a: typing.Union[submodule, ClassConfig[submodule]],
                     b: ClassConfig[submodule]):
            self.a = a if isinstance(a, submodule) else a.build()
            self.b = b.build()

    assert TypeDef.load(ClassConfig[module],
                        {'a': {'a': 1, 'b': 2}, 'b': {'a': 3, 'b': 4, 'c': 5}}).b.c == 5
    assert TypeDef.load(ClassConfig[module],
                        {'a': {'a': 1, 'b': 2}, 'b': {'a': 3, 'b': 4, 'c': 5}}).build().b._c == 5


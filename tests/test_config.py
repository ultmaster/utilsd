import os
from typing import Dict, Union

import pytest
from utilsd.config import ClassConfig, PythonConfig, Registry, RegistryConfig, ValidationError, configclass
from unittest.mock import patch


class Converters(metaclass=Registry, name='converter'):
    pass


@Converters.register_module()
class Converter1:
    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b


@Converters.register_module()
class Converter2:
    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b


@configclass
class Bar(PythonConfig):
    n: int


@configclass
class Foo(PythonConfig):
    a: int
    b: float
    c: Bar


@configclass
class CfgRegistryNormal(PythonConfig):
    m: RegistryConfig[Converters]


@configclass
class CfgRegistryDict(PythonConfig):
    m: Dict[str, RegistryConfig[Converters]]


class InitWithComplexType:
    def __init__(self, converter: Union[Converter1, ClassConfig[Converter1]]):
        if isinstance(converter, Converter1):
            self.converter = converter
        else:
            print(converter)
            self.converter = converter.build()


class DependencyInjectionClass:
    def __init__(self, m: Converter1):
        self.m = m


@configclass
class DependencyInjectionClassType(PythonConfig):
    c: ClassConfig[DependencyInjectionClass]


@configclass
class CfgInitWithComplexType(PythonConfig):
    m: ClassConfig[InitWithComplexType]


@configclass
class FooN(PythonConfig):
    n: ClassConfig[Converter1]


def test_python_config():
    assert Foo(a=1, b=2.0, c={'n': 0}).c.n == 0


def test_python_config_with_extra_kwargs():
    pass
    # TODO
    # config = DependencyInjectionClassType(c={})


def test_registry_config():
    config = CfgRegistryNormal(m={'type': 'Converter1', 'a': 1, 'b': 2})
    assert config.m.a == 1
    assert config.m.type() == Converter1
    assert config.m.build().a == 1
    assert isinstance(config.m.build(), Converter1)


def test_registry_config_complex():
    config = CfgRegistryDict(m=dict(a={'type': 'Converter1', 'a': 1, 'b': 2}, b={'type': 'Converter2', 'a': 3, 'b': 4}))
    assert config.m['a'].type() == Converter1
    assert config.m['b'].type() == Converter2
    assert config.m['a'].a == 1
    assert config.m['b'].a == 3

    assert isinstance(InitWithComplexType(config.m['a']).converter, Converter1)
    assert isinstance(InitWithComplexType(config.m['a'].build()).converter, Converter1)


def test_registry_config_complex_union():
    config = CfgInitWithComplexType(m=dict(converter={'a': 1, 'b': 2}))
    assert isinstance(config.m.build().converter, Converter1)


def test_class_config():
    assert FooN(n={'a': 1, 'b': 2}).n.a == 1
    with pytest.raises(ValidationError):
        FooN(n={'a': 'aaa', 'b': 2})


def test_registry():
    assert len(Converters) == 2
    assert 'Converter1' in Converters
    assert Converters.get('Converter1') == Converter1


def test_parse_command_line():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/exp_config.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp]):
        assert Foo.fromcli().b == 2.0
    with patch('argparse._sys.argv', ['test.py', config_fp, '--b', '3']):
        assert Foo.fromcli().b == 3
    with patch('argparse._sys.argv', ['test.py', config_fp, '--c.n', '1']):
        assert Foo.fromcli().c.n == 1


if __name__ == '__main__':
    test_python_config()
    test_parse_command_line()
    test_registry()
    test_registry_config()
    test_class_config()

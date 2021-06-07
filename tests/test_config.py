import os
from typing import Dict

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


@configclass
class FooN(PythonConfig):
    n: ClassConfig[Converter1]


def test_python_config():
    assert Foo(a=1, b=2.0, c={'n': 0}).c.n == 0


def test_registry_config():
    config = CfgRegistryNormal(m={'type': 'Converter1', 'a': 1, 'b': 2})
    assert config.m.a == 1
    assert config.m.type() == Converter1


def test_registry_config_complex():
    config = CfgRegistryDict(m=dict(a={'type': 'Converter1', 'a': 1, 'b': 2}, b={'type': 'Converter2', 'a': 3, 'b': 4}))
    assert config.m['a'].type() == Converter1
    assert config.m['b'].type() == Converter2
    assert config.m['a'].a == 1
    assert config.m['b'].a == 3


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

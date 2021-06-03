import os
from utilsd.config.registry import RegistryConfig

from utilsd.config import PythonConfig, Registry, RegistryConfig, configclass
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
class FooM(PythonConfig):
    m: RegistryConfig[Converters]


def test_python_config():
    assert Foo(a=1, b=2.0, c={'n': 0}).c.n == 0


def test_registry_config():
    assert FooM(m={'type': 'Converter1', 'a': 1, 'b': 2}).m.a == 1


def test_registry():
    assert len(Converters) == 1
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

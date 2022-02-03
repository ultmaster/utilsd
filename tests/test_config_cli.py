import os
from typing import Optional

import pytest
from utilsd.config import PythonConfig, Registry, RegistryConfig, SubclassConfig, ValidationError, configclass
from unittest.mock import patch
from tests.assets.import_class import BaseBar


class BaseFoo:
    pass


class SubFoo(BaseFoo):
    pass


@configclass
class Bar(PythonConfig):
    n: int


@configclass
class Foo(PythonConfig):
    a: int
    b: float
    c: Bar


@configclass
class CfgWithSubclass(PythonConfig):
    n: SubclassConfig[BaseFoo]
    t: SubclassConfig[BaseBar]


class TEST(metaclass=Registry, name="test"):
    pass


@TEST.register_module()
class TestModule:
    def __init__(self, a: int = 1, b: Optional[str] = None):
        self.a = a
        self.b = b


@configclass
class RegistryModuleConfig(PythonConfig):
    test: RegistryConfig[TEST]


def test_parse_command_line():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/exp_config.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp]):
        assert Foo.fromcli().b == 2.0
    with patch('argparse._sys.argv', ['test.py', config_fp, '--b', '3']):
        assert Foo.fromcli().b == 3
    with patch('argparse._sys.argv', ['test.py', config_fp, '--c.n', '1']):
        assert Foo.fromcli().c.n == 1


def test_parse_command_line_dynamic():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/exp_config_subclass.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp]):
        assert CfgWithSubclass.fromcli().t.build().a == 1
    with patch('argparse._sys.argv', ['test.py', config_fp, '--t.a', '2']):
        assert CfgWithSubclass.fromcli().t.build().a == 2


def test_registry_config_command_line():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/registry1.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp, '--test.a', '2']):
        config = RegistryModuleConfig.fromcli()
        assert config.test.a == 2
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/registry2.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp, '--help']):
        config = RegistryModuleConfig.fromcli()
        # assert config.test.b == 'test'
    with patch('argparse._sys.argv', ['test.py', config_fp, '--test.b', 'test']):
        config = RegistryModuleConfig.fromcli()
        assert config.test.b == 'test'


if __name__ == '__main__':
    test_registry_config_command_line()

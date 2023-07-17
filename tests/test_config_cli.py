import os
from typing import Optional, Union

from utilsd.config import PythonConfig, Registry, RegistryConfig, SubclassConfig, configclass
from unittest.mock import patch
from tests.assets.import_class import BaseBar


class BaseFoo:
    pass


class SubFoo(BaseFoo):
    pass


@configclass
class Bar:
    n: int


@configclass
class Foo:
    a: int
    b: float
    c: Bar


@configclass
class CfgWithSubclass:
    n: SubclassConfig[BaseFoo]
    t: SubclassConfig[BaseBar]


class TEST(metaclass=Registry, name="test"):
    pass


@TEST.register_module()
class Module1:
    def __init__(self, a: int = 1, b: Optional[str] = None, c: Union[str, BaseFoo, None] = None):
        self.a = a
        self.b = b
        self.c = c


@configclass
class RegistryModuleConfig:
    test: RegistryConfig[TEST]


@configclass
class ConfWithBool:
    act: bool


def test_parse_command_line():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/exp_config.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp]):
        assert Foo.fromcli().b == 2.0
    with patch('argparse._sys.argv', ['test.py', config_fp, '--b', '3']):
        assert Foo.fromcli().b == 3
    with patch('argparse._sys.argv', ['test.py', config_fp, '--c.n', '1']):
        assert Foo.fromcli().c.n == 1


def test_cli_with_bool():
    config_fp = os.path.join(os.path.dirname(__file__), 'assets/exp_config_bool.yml')
    with patch('argparse._sys.argv', ['test.py', config_fp]):
        assert ConfWithBool.fromcli().act == False
    with patch('argparse._sys.argv', ['test.py', config_fp, '--act', 'true']):
        assert ConfWithBool.fromcli().act == True
    with patch('argparse._sys.argv', ['test.py', config_fp, '-a', 'true']):
        assert ConfWithBool.fromcli(shortcuts={'act': ['-a']}).act == True


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

    # test optional int, default = None
    with patch('argparse._sys.argv', ['test.py', config_fp, '--test.b', 'test']):
        config = RegistryModuleConfig.fromcli()
        assert config.test.b == 'test'

    # test json
    with patch('argparse._sys.argv', ['test.py', config_fp, '--test', '{"a": 42, "b": "abc"}']):
        config = RegistryModuleConfig.fromcli()
        assert config.test.a == 42
        assert config.test.b == 'abc'


if __name__ == '__main__':
    # test_cli_with_bool()
    test_registry_config_command_line()

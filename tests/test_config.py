import os

from utilsd.config import PythonConfig, configclass
from unittest.mock import patch


@configclass
class Bar(PythonConfig):
    n: int


@configclass
class Foo(PythonConfig):
    a: int
    b: float
    c: Bar


def test_python_config():
    assert Foo(a=1, b=2.0, c={'n': 0}).c.n == 0


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

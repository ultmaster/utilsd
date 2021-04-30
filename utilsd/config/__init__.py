from dataclasses import dataclass
from functools import partial

from .builtin import RuntimeConfig
from .python import PythonConfig

configclass = partial(dataclass, init=False)


__all__ = ['PythonConfig', 'RuntimeConfig', 'configclass']

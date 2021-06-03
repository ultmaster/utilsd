from dataclasses import dataclass
from functools import partial

from .builtin import RuntimeConfig
from .python import PythonConfig
from .registry import Registry, RegistryConfig

configclass = partial(dataclass, init=False)


__all__ = ['PythonConfig', 'RuntimeConfig', 'Registry', 'RegistryConfig', 'configclass']

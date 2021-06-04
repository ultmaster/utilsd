from dataclasses import dataclass
from functools import partial

from .builtin import RuntimeConfig
from .exception import ValidationError
from .python import PythonConfig, RegistryConfig, ClassConfig
from .registry import Registry

configclass = partial(dataclass, init=False)


__all__ = ['ClassConfig', 'PythonConfig', 'RuntimeConfig', 'Registry',
           'RegistryConfig', 'ValidationError', 'configclass']

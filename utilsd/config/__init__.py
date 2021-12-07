from dataclasses import dataclass

from .builtin import RuntimeConfig
from .exception import ValidationError
from .python import PythonConfig, RegistryConfig, ClassConfig, SubclassConfig
from .registry import Registry

configclass = dataclass(init=False)


__all__ = ['ClassConfig', 'PythonConfig', 'RuntimeConfig', 'Registry',
           'RegistryConfig', 'SubclassConfig', 'ValidationError', 'configclass']

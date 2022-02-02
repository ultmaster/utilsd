# Modified from https://github.com/open-mmlab/mmcv/blob/master/mmcv/utils/registry.py

import inspect
from typing import Optional, Type, Union


class Registry(type):
    def __new__(cls, clsname, bases, attrs, name=None):
        # registry is a type here because it needs to be used in RegistryClass.
        assert name is not None, 'Registry must have a name.'
        cls = super().__new__(cls, clsname, bases, attrs)
        cls._name = name
        cls._module_dict = {}
        return cls

    @property
    def name(cls):
        return cls._name

    @property
    def module_dict(cls):
        return cls._module_dict

    def __len__(cls):
        return len(cls._module_dict)

    def __contains__(cls, key):
        return cls.get(key) is not None

    def __repr__(cls):
        format_str = cls.__name__ + f'(name={cls._name}, items={cls._module_dict})'
        return format_str

    def get(cls, key):
        if key in cls._module_dict:
            return cls._module_dict[key]

    def _register_module(cls, module_class, module_name=None, force=False):
        if not inspect.isclass(module_class):
            raise TypeError(f'module must be a class, but got {type(module_class)}')

        if module_name is None:
            module_name = module_class.__name__
        if isinstance(module_name, str):
            module_name = [module_name]
        for name in module_name:
            if not force and name in cls._module_dict:
                raise KeyError(f'{name} is already registered in {cls.name}')
            cls._module_dict[name] = module_class

    def register_module(cls, name: Optional[str] = None, force: bool = False, module: Type = None):
        if not isinstance(force, bool):
            raise TypeError(f'force must be a boolean, but got {type(force)}')

        # raise the error ahead of time
        if not (name is None or isinstance(name, str) or (
                isinstance(name, list) and all([isinstance(n, str) for n in name]))):
            raise TypeError('name must be either of None, an instance of str or a sequence'
                            f' of str, but got {type(name)}')

        # use it as a normal method: x.register_module(module=SomeClass)
        if module is not None:
            cls._register_module(module_class=module, module_name=name, force=force)
            return module

        # use it as a decorator: @x.register_module()
        def _register(reg_cls):
            cls._register_module(module_class=reg_cls, module_name=name, force=force)
            return reg_cls

        return _register

    def unregister_module(cls, name_or_module: Union[str, Type]):
        if isinstance(name_or_module, str):
            if name_or_module not in cls._module_dict:
                raise KeyError(f'{name_or_module} is not found in {cls.name}')
            cls._module_dict.pop(name_or_module)
        else:
            to_remove = [k for k, v in cls._module if v == name_or_module]
            if not to_remove:
                raise KeyError(f'{name_or_module} is not found in {cls.name}')
            for k in to_remove:
                cls._module_dict.pop(k)

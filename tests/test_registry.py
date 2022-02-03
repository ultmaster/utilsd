from typing import Dict, Union

import pytest
from utilsd.config import ClassConfig, Registry, RegistryConfig, SubclassConfig, configclass
from utilsd.config.type_def import TypeDef
from tests.assets.import_class import BaseBar


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


class BaseFoo:
    pass


class SubFoo(BaseFoo):
    pass


@configclass
class CfgRegistryNormal:
    m: RegistryConfig[Converters]


@configclass
class CfgRegistryDict:
    m: Dict[str, RegistryConfig[Converters]]


class InitWithComplexType:
    def __init__(self, converter: Union[Converter1, ClassConfig[Converter1]]):
        if isinstance(converter, Converter1):
            self.converter = converter
        else:
            self.converter = converter.build()


class InitWithComplexTypeSubclass:
    def __init__(self, converter: Union[BaseFoo, SubclassConfig[BaseFoo]]):
        if isinstance(converter, BaseFoo):
            self.converter = converter
        else:
            self.converter = converter.build()


@configclass
class CfgInitWithComplexType:
    m: ClassConfig[InitWithComplexType]


@configclass
class CfgInitWithComplexTypeSubclass:
    m: ClassConfig[InitWithComplexTypeSubclass]


@configclass
class FooN:
    n: ClassConfig[Converter1]


@configclass
class CfgWithSubclass:
    n: SubclassConfig[BaseFoo]
    t: SubclassConfig[BaseBar]


def test_registry_config():
    config = TypeDef.load(CfgRegistryNormal, dict(m={'type': 'Converter1', 'a': 1, 'b': 2}))
    assert config.m.a == 1
    assert config.m.type() == Converter1
    assert config.m.build().a == 1
    assert isinstance(config.m.build(), Converter1)


def test_registry_config_complex():
    config = TypeDef.load(
        CfgRegistryDict,
        dict(m=dict(a={'type': 'Converter1', 'a': 1, 'b': 2}, b={'type': 'Converter2', 'a': 3, 'b': 4}))
    )
    assert config.m['a'].type() == Converter1
    assert config.m['b'].type() == Converter2
    assert config.m['a'].a == 1
    assert config.m['b'].a == 3

    assert isinstance(InitWithComplexType(config.m['a']).converter, Converter1)
    assert isinstance(InitWithComplexType(config.m['a'].build()).converter, Converter1)


def test_registry_config_complex_union():
    config = TypeDef.load(CfgInitWithComplexType, dict(m=dict(converter={'a': 1, 'b': 2})))
    assert isinstance(config.m.build().converter, Converter1)


def test_registry_config_complex_subclass_union():
    config = TypeDef.load(CfgInitWithComplexTypeSubclass, dict(m=dict(converter=dict(type='SubFoo'))))
    assert isinstance(config.m.build().converter, SubFoo)


def test_subclass_config():
    config = TypeDef.load(CfgWithSubclass, dict(
        n={'type': 'SubFoo'},
        t={'type': 'tests.assets.import_invisible.SubBar', 'a': 1}
    ))
    assert isinstance(config.t.build(), BaseBar)
    assert isinstance(config.n.build(), SubFoo)
    assert config.t.build().a == 1


def test_registry():
    assert len(Converters) == 2
    assert 'Converter1' in Converters
    assert Converters.get('Converter1') == Converter1

    assert Converters.inverse_get(Converter1) == 'Converter1'
    Converters.unregister_module(Converter2)
    assert len(Converters) == 1

    with pytest.raises(KeyError):
        Converters.unregister_module('Converter2')
    Converters.register_module(module=Converter2)
    Converters.unregister_module('Converter2')
    assert len(Converters) == 1

    Converters.register_module(module=Converter2)
    assert len(Converters) == 2

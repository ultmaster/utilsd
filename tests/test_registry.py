from typing import Dict, Union

import pytest
from utilsd.config import ClassConfig, Registry, RegistryConfig, SubclassConfig, configclass
from utilsd.config.type_def import TypeDef
from utilsd.config.exception import ValidationError
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
    assert TypeDef.dump(CfgRegistryDict, config) == \
        dict(m=dict(a={'type': 'Converter1', 'a': 1, 'b': 2}, b={'type': 'Converter2', 'a': 3, 'b': 4}))
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

    assert TypeDef.dump(CfgWithSubclass, config) == dict(
        n={'type': 'tests.test_registry.SubFoo'},
        t={'type': 'tests.assets.import_invisible.SubBar', 'a': 1}
    )
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


class TestInhReg(metaclass=Registry, name='TestInh'):
    pass


@TestInhReg.register_module()
class InhBase():
    def __init__(self, a: int, b: int, **kwargs):
        self.a = a
        self.b = b
        self.uncollected = kwargs
        

@TestInhReg.register_module(inherent=True)
class InhChild1(InhBase):
    def __init__(self, c: int, d: int, **kwargs):
        super().__init__(**kwargs)
        self.c = c
        self.d = d


@TestInhReg.register_module()
class InhChild2(InhBase):
    def __init__(self, c: int, d: int, **kwargs):
        super().__init__(**kwargs)
        self.c = c
        self.d = d


@configclass
class InhRegCfg:
    m: RegistryConfig[TestInhReg]


def test_superclass_registry():
    assert len(TestInhReg) == 3
    assert "InhChild1" in TestInhReg
    assert "InhChildNotDefined" not in TestInhReg

    # when inherent is set True, the module will look back to its super class for areas
    config = TypeDef.load(
        InhRegCfg, dict(m=dict(type="InhChild1", a=1, b=2, c=3, d=4))
    )
    child1 = config.m.build()
    assert child1.a == 1
    assert child1.c == 3

    with pytest.raises(ValidationError):
        # when inherent is set False (default), all the keys must be specifed in the param list of __init__
        config = TypeDef.load(
            InhRegCfg, dict(m=dict(type="InhChild2", a=1, b=2, c=3, d=4))
        )

from utilsd.config import Registry


class DummyReg(metaclass=Registry, name="test"):
    pass

@DummyReg.register_module()
class Reg():
    def __init__(self, a: int, b: str):
        self.a = a
        self.b = b

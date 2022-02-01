from enum import Enum


class MyEnum(str, Enum):
    state1 = 'state1_val'
    state2 = 'state2_val'

print(MyEnum('state1_val').value)
import random
import string


def random_key():
    return ''.join([random.choice('abcdef' + string.digits) for _ in range(30)])

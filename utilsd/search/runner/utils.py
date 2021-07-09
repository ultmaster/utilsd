import random
import string


def random_key():
    return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(30)])

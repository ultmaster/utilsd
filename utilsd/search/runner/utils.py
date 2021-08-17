import random
import string


def random_key():
    return ''.join([random.choice('abcdef' + string.digits) for _ in range(30)])


def kill_pid(pid):
    import psutil
    process = psutil.Process(pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()

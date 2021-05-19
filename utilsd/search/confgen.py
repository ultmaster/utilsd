  
import copy
import itertools
import random

import numpy as np

from .space import Choice


def flatten_search_space(search_space):
    # keep choices only
    def _flatten(s, prefix):
        if isinstance(s, dict):
            for k, v in s.items():
                if isinstance(v, Choice):
                    t[prefix + k] = v
                else:
                    _flatten(v, prefix + k + '.')
        elif isinstance(s, list):
            for k, v in enumerate(s):
                if isinstance(v, Choice):
                    t[prefix + str(k)] = v
                else:
                    _flatten(v, prefix + str(k) + '.')

    t = {}
    _flatten(search_space, '')
    return t


def flatten_config(config):
    def _flatten(c, prefix):
        if isinstance(c, (str, float, int, tuple)):
            t[prefix[:-1]] = c
        elif isinstance(c, dict):
            for k, v in c.items():
                _flatten(v, prefix + k + '.')
        elif isinstance(c, list):
            for k, v in enumerate(c):
                _flatten(v, prefix + str(k) + '.')

    t = {}
    _flatten(config, '')
    return t


def restore_config(flattened_config, search_space):
    # restore back. Use search space as template.
    config = copy.deepcopy(search_space)
    for k, v in flattened_config.items():
        location = config
        steps = [int(step) if step.isdigit() else step for step in k.split('.')]
        try:
            for step in steps[:-1]:
                location = location[step]
            if not isinstance(location, dict) or steps[-1] in location:
                location[steps[-1]] = v
        except KeyError:
            pass
    return config


def default_convert(config):
    config['_meta'] = copy.deepcopy(config)
    config.setdefault('runtime', {})
    config['runtime']['seed'] = random.randint(0, 10000)
    return config


def grid_search(search_space):
    flattened = flatten_search_space(search_space)
    flattened = [[(k, t) for t in v] for k, v in flattened.items()]
    for d in itertools.product(*flattened):
        yield restore_config(dict(d), search_space)


def random_search(search_space):
    # Assuming the search space is not large. Otherwise this will not work.
    flattened = flatten_search_space(search_space)
    flattened = [[(k, t) for t in v] for k, v in flattened.items()]
    search_space_size = np.product([len(a) for a in flattened])
    print('Search space size:', search_space_size)
    assert search_space_size < 1e7
    full_list = list(itertools.product(*flattened))
    random.shuffle(full_list)
    for d in full_list:
        yield restore_config(dict(d), search_space)

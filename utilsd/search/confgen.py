import random
from typing import Any, Optional

from .space import sample_from, iterate_over, size
from ..fileio import dump


def shuffle_(lst):
    random.shuffle(lst)
    return lst


def offline_search(space: Any, budget: int, method: str = 'random', out_file: Optional[Any] = None):
    if method == 'random':
        if size(space) < 1e6:
            samples = shuffle_(list(iterate_over(space)))[:budget]
        else:
            samples = [sample_from(space) for _ in range(budget)]
    elif method == 'grid':
        samples = shuffle_(list(iterate_over(space)))[:budget]
    else:
        raise ValueError(f'Unsupported method: {method}')
    if out_file is not None:
        dump(samples, out_file)
    return samples

import abc
import copy
import itertools
import random
from typing import Any, List, Optional


class Space(abc.ABC):
    @abc.abstractmethod
    def sample(self):
        pass


class Choice(Space):
    def __init__(self, choices: List[Any], prior: Optional[List[float]] = None):
        self.choices = choices
        self.prior = prior

    def __repr__(self):
        return f'Choices({self.choices})'

    def sample(self, excludes=None, retry=100):
        if excludes is None:
            excludes = []
        if len(excludes) >= len(self.choices):
            raise ValueError(f'Too many excludes: {excludes}')
        for _ in range(retry):
            if self.prior is not None:
                picked = random.choices(self.choices, self.prior, k=1)[0]
            else:
                picked = random.choice(self.choices)
            if picked not in excludes:
                return picked
        raise ValueError(f'Too many retries to pick from {self.choices} that excludes {excludes}')

    def __iter__(self):
        return iter(self.choices)

    def __len__(self):
        return len(self.choices)


def size(space: Any):
    sz = 1
    def _measure(space: Any):
        nonlocal sz
        if isinstance(space, Space):
            sz *= len(space)
        if isinstance(space, (tuple, list)):
            [_measure(s) for s in space]
        if isinstance(space, dict):
            [_measure(s) for s in space.values()]

    _measure(space)
    return sz


def sample_from(space: Any):
    meta = {}
    def _sample(key: str, space: Any):
        if isinstance(space, Space):
            sample = space.sample()
            meta[key] = sample
            return sample
        if isinstance(space, list):
            return [_sample(_joinkey(key, i), s) for i, s in enumerate(space)]
        if isinstance(space, tuple):
            return tuple([_sample(_joinkey(key, i), s) for i, s in enumerate(space)])
        if isinstance(space, dict):
            return {k: _sample(_joinkey(key, k), v) for k, v in space.items()}
        return space

    sample = _sample('', space)
    sample['_meta'] = meta
    return sample


def iterate_over(space: Any):
    meta = {}
    def _iterate(key: str, space: Any):
        if isinstance(space, Space):
            for sample in space:
                meta[key] = sample
                yield sample
        elif isinstance(space, list):
            for sample in _product(*[(_joinkey(key, i), s) for i, s in enumerate(space)]):
                yield list(sample)
        elif isinstance(space, tuple):
            for sample in _product(*[(_joinkey(key, i), s) for i, s in enumerate(space)]):
                yield tuple(sample)
        elif isinstance(space, dict):
            keys, values = list(zip(*space.items()))
            for sample in _product(*[(_joinkey(key, k), s) for k, s in zip(keys, values)]):
                yield dict(zip(keys, sample))
        else:
            yield space

    def _product(*iterate_params):
        if len(iterate_params) == 1:
            for s in _iterate(*iterate_params[0]):
                yield (s,)
        else:
            for s in _iterate(*iterate_params[0]):
                for t in _product(*iterate_params[1:]):
                    yield (s,) + t

    for sample in _iterate('', space):
        sample['_meta'] = copy.deepcopy(meta)
        yield sample


def _joinkey(a, b):
    return f'{a}.{b}' if str(a) else str(b)

import pickle
from pathlib import Path
from typing import NoReturn

from .runner import RUNNERS


class Tuner:
    def __init__(self, exp_dir: Path, runner: str):
        self.exp_dir = exp_dir
        self.runner = RUNNERS.get(runner)(exp_dir)

        self.resume()

    @property
    def checkpoint_path(self) -> Path:
        return self.exp_dir / 'checkpoint.pt'

    def resume(self):
        data = pickle.load(self.checkpoint_path.open('rb'))
        self.runner.load(data['runner'])

    def checkpoint(self) -> NoReturn:
        data = {
            'runner': self.runner.dump()
        }
        pickle.dump(data, self.checkpoint_path.open('wb'))


class Random(Tuner):
    def __init__(self, exp_dir: Path, runner: str, budget: int)

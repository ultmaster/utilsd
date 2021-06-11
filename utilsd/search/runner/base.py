import abc
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


OUTPUT_DIR_ENV_KEY = 'PT_OUTPUT_DIR'


@dataclass
class Trial:
    sequence_id: int
    command: str
    status: Literal['pass', 'failed', 'running', 'queued'] = 'queued'
    output_dir: Optional[Path] = None


@abc.ABC
class BaseRunner:
    def __init__(self, exp_dir: Path, trials: Optional[List[Trial]] = None):
        self.exp_dir = exp_dir
        assert self.exp_dir.exists(), f'Experiment dir {self.exp_dir} does not exist.'
        self.trials = trials or []

    @abc.abstractmethod
    def submit_trials(*trials: Trial):
        pass

    @abc.abstractmethod
    def wait_trials(*trials: Trial):
        pass

    def resume(self, data: Dict[str, Any]):
        self.trials = [Trial.load(t) for t in data['trials']]

    def checkpoint(self) -> Dict[str, Any]:
        return {
            'trials': [t.dump() for t in self.trials]
        }

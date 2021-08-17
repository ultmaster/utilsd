import abc
import click
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from utilsd.config import Registry


OUTPUT_DIR_ENV_KEY = 'PT_OUTPUT_DIR'


@click.group()
def runner_cli():
    pass


class RUNNERS(metaclass=Registry, name='runners'):
    pass


@dataclass
class MetricData:
    metric: Any
    timestamp: float
    sequence: int


@dataclass
class Trial:
    sequence_id: int
    command: str
    status: Literal['pass', 'failed', 'killed', 'running', 'queued'] = 'queued'
    output_dir: Optional[Path] = None
    metrics: List[MetricData] = field(default_factory=list)
    job_tracking_info: Any = None
    retry_count: int = 0

    def completed(self):
        return self.status in ['pass', 'failed', 'killed']


class BaseRunner(abc.ABC):
    def __init__(self, exp_dir: Path):
        self.exp_dir = exp_dir
        assert self.exp_dir.exists(), f'Experiment dir {self.exp_dir} does not exist.'
        self.trials: List[Trial] = []

    @abc.abstractmethod
    def submit_trials(self, *trials: Trial):
        pass

    @abc.abstractmethod
    def wait_trials(self, *trials: Trial):
        pass

    @abc.abstractmethod
    def kill_trials(self, *trials: Trial):
        pass

    @abc.abstractstaticmethod
    def run_trial(cls):
        pass

    def load(self, data: Dict[str, Any]):
        self.trials = [Trial.load(t) for t in data['trials']]

    def dump(self) -> Dict[str, Any]:
        return {
            'trials': [t.dump() for t in self.trials]
        }

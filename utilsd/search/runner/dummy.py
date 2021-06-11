import subprocess
from pathlib import Path
from typing import List

from .base import BaseRunner, Trial, OUTPUT_DIR_ENV_KEY


class DummyRunner(BaseRunner):
    def __init__(self, exp_dir: Path):
        super().__init__(exp_dir=exp_dir)

    def submit_trials(self, *trials: Trial):
        for trial in trials:
            trial.status = 'running'
            trial.output_dir = (self.exp_dir / str(trial.sequence_id))
            subproc = subprocess.run(trial.command, shell=True,
                                     env={OUTPUT_DIR_ENV_KEY: trial.output_dir.as_posix()})
            if subproc.returncode == 0:
                trial.status = 'pass'
            else:
                trial.status = 'failed'



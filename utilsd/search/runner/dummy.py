import subprocess
import warnings
from pathlib import Path

from .base import BaseRunner, Trial, OUTPUT_DIR_ENV_KEY, RUNNERS


@RUNNERS.register_module('dummy')
class DummyRunner(BaseRunner):
    def __init__(self, exp_dir: Path):
        super().__init__(exp_dir=exp_dir)

    def submit_trials(self, *trials: Trial):
        for trial in trials:
            trial.output_dir = (self.exp_dir / str(trial.sequence_id))
            self.trials.append(trial)
            trial.status = 'running'
            subproc = subprocess.run(trial.command, shell=True,
                                     env={OUTPUT_DIR_ENV_KEY: trial.output_dir.as_posix()})
            if subproc.returncode == 0:
                trial.status = 'pass'
            else:
                trial.status = 'failed'

    def wait_trials(self, *trials: Trial):
        pass

    def resume(self, data):
        super().resume(data)
        for trial in self.trials:
            if trial.completed():
                warnings.warn(f'Trial is not completed. Will not be resumed: {trial}')

    @classmethod
    def run_trial(cls):

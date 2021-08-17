import dataclasses
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from utilsd.logging import print_log

from .base import BaseRunner, Trial


def run_commands(trials: Dict[str, str], runner: BaseRunner, out_file: Optional[Path] = None):
    expanded_trials = []
    for i, (name, trial) in enumerate(trials.items()):
        expanded_trials.append(Trial(sequence_id=i, command=trial, output_dir=runner.exp_dir / name))
    try:
        runner.submit_trials(*expanded_trials)
        while True:
            left_trials = [t for t in expanded_trials if not t.completed()]
            runner.wait_trials(*left_trials)
            print_log(f'Left trials: {len(left_trials)}', __name__)
            if out_file is not None:
                pd.DataFrame.from_records([dataclasses.asdict(trial) for trial in expanded_trials]).to_csv(out_file)
            if not left_trials:
                break
            time.sleep(10)
    except KeyboardInterrupt:
        print_log('Interrupted. kill left trials...')
        runner.kill_trials(*expanded_trials)

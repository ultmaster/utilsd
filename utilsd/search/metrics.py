import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from .runner.base import MetricData
from utilsd.logging import print_log
from utilsd.experiment import get_output_dir


_step_count = 0


def report_metric(metric: Any, step: Optional[int] = None):
    global _step_count
    if step is None:
        _step_count = step
    _step_count += 1
    metric_data = asdict(MetricData(metric, datetime.now().timestamp(), step))
    try:
        with (get_output_dir() / '.metrics').open('a') as f:
            print(json.dumps(metric_data), f)
    except AssertionError:
        print_log(f'[Local mode] Metric: {metric_data}', __name__)

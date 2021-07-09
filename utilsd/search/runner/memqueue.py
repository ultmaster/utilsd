import json
import os
import threading
from pathlib import Path
from typing import Optional

from utilsd.logging import print_log
from .base import BaseRunner, RUNNERS, Trial
from .utils import random_key

_lock = threading.Lock()


@RUNNERS.register_module('memqueue')
class MemQueueRunner(BaseRunner):
    """
    MemQueue runner that is based on the synchronization of a redis server.

    Workers should be launched via ``python -m utilsd.search.runner.memqueue /path/to/your/expdir --host <host> --port <port>``.
    If you are in local code, host and port can be omitted, which will be localhost:6379 by default.
    """

    def __init__(self, exp_dir: Path, host: Optional[str] = None, port: int = 6379):
        super().__init__(exp_dir)

        if host is None:
            host = self._get_default_ip()

        from redis import Redis
        self._redis_server = Redis(host, port)

    def _get_default_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('1.1.1.1', 1))
        default_ip = s.getsockname()[0]
        print_log(f'Detecting default IP: {default_ip}', __name__)
        return default_ip

    def submit_trials(self, *trials: Trial):
        try:
            _lock.acquire()
            for trial in trials:
                self._send_to_redis(trial)
        finally:
            _lock.release()

    def wait_trials(self, *trials: Trial):
        for trial in trials:
            redis_cache_key_name = 'utilsd_status_' + trial.job_tracking_info['job_id']
            status = self._redis_server.get(redis_cache_key_name)
            if status is not None:
                status = json.loads(status.decode())
                trial.job_tracking_info.update(status)
                if status['pid'] is None:
                    trial.status = 'queued'
                else:
                    trial.output_dir = status['output_dir']
                    if status['exitcode'] is None:
                        trial.status = 'running'
                    elif status['exitcode'] == 0:
                        trial.status == 'success'
                    else:
                        trial.status = 'failed'
                self._redis_server.delete(redis_cache_key_name)

            redis_cache_key_name = 'utilsd_metrics_' + trial.job_tracking_info['job_id']
            metric = self._redis_server.lpop(redis_cache_key_name)
            if metric is not None:
                metric = json.loads(metric.decode())
                self._logger.info(f'[Trial #{pid}] Collected metrics: {metric}')
                if metric['type'] == 'final':
                    self._metrics[pid] = metric['value']
                    break
            else:
                break

    def _send_to_redis(self, trial: Trial):
        try:
            _lock.acquire()
            job_id = random_key()
            trial.output_dir = 
            trial.job_tracking_info = {'job_id': job_id}
            task = {
                'id': job_id,
                'command': trial.command
            }
            trial.status = 'queued'
            self._redis_server.rpush('utilsd_tasks', json.dumps(task))
        finally:
            _lock.release()

    def submit_new_trial(self, command, parameters, setup=None):
        try:
            _lock.acquire()
            parameter_id = self._parameter_id
            self._parameter_id += 1
            task = {
                'prepare': setup,
                'command': command,
                'exp_id': self._experiment_id,
                'trial_id': str(parameter_id),
                'seq_id': parameter_id,
                'parameters': parameters
            }
            self._logger.info(f'Generated new task with pid {parameter_id}: {task}')
            self._redis_server.rpush('tasks', json.dumps(task))
            self.history.append(task)
            self._statuses[parameter_id] = TrialStatus.RUNNING
            return parameter_id
        finally:
            _lock.release()

    def _collect_new_metrics(self, pid):
        while True:
            metric = self._redis_server.lpop(f'metrics_{self._experiment_id}_{pid}')
            if metric is not None:
                metric = json.loads(metric.decode())
                self._logger.info(f'[Trial #{pid}] Collected metrics: {metric}')
                if metric['type'] == 'final':
                    self._metrics[pid] = metric['value']
                    break
            else:
                break

    def _collect_new_statuses(self, pid):
        status = self._redis_server.get(f'status_{self._experiment_id}_{pid}')
        if status is not None:
            status = json.loads(status.decode())
            self._logger.info(f'[Trial #{pid}] Collected status: {status}')
            self._statuses[pid] = TrialStatus.SUCCESS if status['exitcode'] == 0 else TrialStatus.FAILED

    def query_metrics(self, pid):
        try:
            _lock.acquire()
            self._collect_new_metrics(pid)
            self._collect_new_statuses(pid)
        finally:
            _lock.release()
        if self._statuses[pid] == TrialStatus.FAILED:
            raise TrialFailed
        elif self._statuses[pid] == TrialStatus.SUCCESS:
            self._logger.warning(f'[Trial #{pid}] succeeded with no metrics.')
            if pid not in self._metrics:
                raise TrialFailed
            return self._metrics[pid]
        return None

    def statistics(self):
        return dict(collections.Counter(self._statuses.values()))
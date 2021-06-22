import json
import os
import threading
from pathlib import Path

from .base import BaseRunner, RUNNERS, Trial

_lock = threading.Lock()


@RUNNERS.register_module('memqueue')
class MemQueueRunner(BaseRunner):

    def __init__(self, exp_dir: Path):
        super().__init__(exp_dir)

        from redis import Redis
        self._redis_server = Redis(
            os.environ.get('REDIS_SERVER', self._get_default_ip()),
            os.environ.get('REDIS_PORT', 6379)
        )

    def _get_default_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('1.1.1.1', 1))
        return s.getsockname()[0]

    def submit_trials(self, *trials: Trial):
        try:
            _lock.acquire()
            for trial in trials:
                task = {'id': trial.sequence_id, 'command': trial.command}
                self._redis_server.rpush('tasks', json.dumps(task))
        finally:
            _lock.release()

    def wait_trials(*trials: Trial):
        # print trial summary


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
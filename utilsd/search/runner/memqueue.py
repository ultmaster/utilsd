import click
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from utilsd.logging import print_log
from .base import BaseRunner, RUNNERS, Trial, OUTPUT_DIR_ENV_KEY, runner_cli
from .utils import random_key

_lock = threading.Lock()


@RUNNERS.register_module('memqueue')
class MemQueueRunner(BaseRunner):
    """
    MemQueue runner that is based on the synchronization of a redis server.

    Workers should be launched via ``python -m utilsd.search.runner memqueue --host <host> --port <port>``
    under your working directory.
    If you are in local code, host and port can be omitted, which will be localhost:6379 by default.
    """

    def __init__(self, exp_dir: Path, host: Optional[str] = None, port: int = 6379, max_retries: int = 2):
        super().__init__(exp_dir)

        if host is None:
            host = self._get_default_ip()

        from redis import Redis
        self._redis_server = Redis(host, port)
        self.max_retries = max_retries

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
        try:
            _lock.acquire()
            for trial in trials:
                if trial.completed():
                    continue
                job_id = trial.job_tracking_info['job_id']
                redis_cache_key_name = 'utilsd_status_' + job_id
                status = self._redis_server.get(redis_cache_key_name)
                if status is not None:
                    self._redis_server.delete(redis_cache_key_name)  # TODO: don't do in multiprocessing
                    status = json.loads(status.decode())
                    trial.job_tracking_info.update(status)
                    if status['pid'] is None:
                        trial.status = 'queued'
                    else:
                        if status.get('exitcode') is None:
                            trial.status = 'running'
                        elif status['exitcode'] == 0:
                            trial.status = 'pass'
                        else:
                            if trial.retry_count < self.max_retries:
                                trial.retry_count += 1
                                print_log(f'[Trial #{trial.sequence_id}] Retry {trial.retry_count}/{self.max_retries}.',
                                          __name__)
                                self._send_to_redis(trial)
                            else:
                                trial.status = 'failed'

                redis_cache_key_name = 'utilsd_metrics_' + job_id
                while True:
                    metric = self._redis_server.lpop(redis_cache_key_name)
                    if metric is not None:
                        metric = json.loads(metric.decode())
                        self._logger.info(f'[Trial #{trial.sequence_id}] Collected metrics: {metric}')
                        trial.metrics.append(metric)
                    else:
                        break
        finally:
            _lock.release()

    def kill_trials(self, *trials: Trial):
        try:
            _lock.acquire()
            for trial in trials:
                if trial.completed():
                    continue
                print_log(f'[Trial #{trial.sequence_id}] Killing.')
                self._redis_server.set('utilsd_kill_' + trial.job_tracking_info['job_id'], 1)
        finally:
            _lock.release()

    def _send_to_redis(self, trial: Trial):
        job_id = random_key()
        trial.job_tracking_info = {'job_id': job_id}
        task = {
            'id': job_id,
            'command': trial.command,
            'output_dir': trial.output_dir.as_posix(),
        }
        trial.status = 'queued'
        self._redis_server.rpush('utilsd_tasks', json.dumps(task))

    @staticmethod
    @runner_cli.command('memqueue')
    @click.argument('host')
    @click.argument('port')
    def run_trial(host: str, port: int):
        from redis import Redis
        _redis_server = Redis(host, port)
        while True:
            next_trial = _redis_server.lpop('utilsd_tasks')
            if next_trial is not None:
                next_trial = json.loads(next_trial.decode())
                print_log(f'Receiving task: {next_trial}', __name__)
                kill_trial_key = 'utilsd_kill_' + next_trial['id']

                kill_command = _redis_server.get(kill_trial_key)
                if kill_command is not None:
                    _redis_server.delete(kill_trial_key)
                    print_log(f'Task is already marked as killed. Continue.', __name__)
                    continue

                process = subprocess.Popen(
                    next_trial['command'],
                    env={**os.environ, OUTPUT_DIR_ENV_KEY: next_trial['output_dir']},
                    shell=True
                )
                status = {'status': 'queued', 'pid': process.pid}

                while True:
                    kill_command = _redis_server.get(kill_trial_key)
                    if kill_command is not None:
                        print_log(f'Kill command received. Killing.', __name__)
                        _redis_server.delete(kill_trial_key)
                        process.kill()

                    if process.poll() is None:
                        new_status = {
                            'pid': process.pid
                        }
                    else:
                        new_status = {
                            'exitcode': process.returncode,
                            'pid': process.pid
                        }
                    if new_status != status:
                        _redis_server.set(
                            'utilsd_status_' + next_trial['id'],
                            json.dumps(new_status)
                        )
                        status = new_status

                    if process.returncode is not None:
                        break
                    time.sleep(5)
                # TODO: metrics
            else:
                time.sleep(5)

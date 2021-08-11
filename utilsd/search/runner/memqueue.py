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
        try:
            _lock.acquire()
            for trial in trials:
                job_id = trial.job_tracking_info['job_id']
                redis_cache_key_name = 'utilsd_status_' + job_id
                status = self._redis_server.get(redis_cache_key_name)
                if trial.completed():
                    continue
                if status is not None:
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
                            trial.status = 'failed'
                    # self._redis_server.delete(redis_cache_key_name)  # FIXME: this has problems

                redis_cache_key_name = 'utilsd_metrics_' + job_id
                while True:
                    metric = self._redis_server.lpop(redis_cache_key_name)
                    if metric is not None:
                        metric = json.loads(metric.decode())
                        self._logger.info(f'[Trial #{job_id}] Collected metrics: {metric}')
                        trial.metrics.append(metric)
                    else:
                        break
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
                process = subprocess.Popen(
                    next_trial['command'],
                    env={**os.environ, OUTPUT_DIR_ENV_KEY: next_trial['output_dir']},
                    shell=True
                )
                status = {'status': 'queued', 'pid': process.pid}
                while True:
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

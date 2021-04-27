import dataclasses
import json
import logging
import os
import pprint
import random
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from .config.builtin import RuntimeConfig
from .logging import print_log, setup_logger, reset_logger

_runtime_config: Optional[RuntimeConfig] = None


def seed_everything(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True


def setup_distributed_training():
    if 'OMPI_COMM_WORLD_SIZE' in os.environ:
        world_size = int(os.environ['OMPI_COMM_WORLD_SIZE'])
        global_rank = int(os.environ['OMPI_COMM_WORLD_RANK'])
        master_uri = "tcp://%s:%s" % (os.environ['MASTER_ADDR'], os.environ['MASTER_PORT'])
        torch.distributed.init_process_group(
            backend='nccl',
            init_method=master_uri,
            world_size=world_size,
            rank=global_rank
        )
        local_rank = int(os.environ['OMPI_COMM_WORLD_LOCAL_RANK'])
        assert local_rank < torch.cuda.device_count()
        torch.cuda.set_device(local_rank)
        return local_rank
    elif 'LOCAL_RANK' in os.environ:
        # launched via torch.distributed.launch --use_env --module
        torch.distributed.init_process_group(backend='nccl',
                                             init_method='env://')
        local_rank = int(os.environ['LOCAL_RANK'])
        assert local_rank < torch.cuda.device_count()
        torch.cuda.set_device(local_rank)
        return local_rank


def setup_experiment(runtime_config: RuntimeConfig, enable_nni: bool = False) -> RuntimeConfig:
    setup_distributed_training()
    seed_everything(runtime_config.seed)

    if runtime_config.output_dir is None:
        if 'PT_OUTPUT_DIR' in os.environ:
            runtime_config.output_dir = Path(os.environ['PT_OUTPUT_DIR'])
        else:
            runtime_config.output_dir = Path('./outputs')

    if enable_nni:
        import nni
        if nni.get_experiment_id() != 'STANDALONE':
            runtime_config.output_dir = runtime_config.output_dir / nni.get_experiment_id() / str(nni.get_sequence_id())

    runtime_config.output_dir.mkdir(exist_ok=True)

    if runtime_config.checkpoint_dir is None:
        runtime_config.checkpoint_dir = runtime_config.output_dir / 'checkpoints'
        runtime_config.checkpoint_dir.mkdir(exist_ok=True)

    if runtime_config.tb_log_dir is None:
        runtime_config.tb_log_dir = runtime_config.output_dir / 'checkpoints'
        runtime_config.tb_log_dir.mkdir(exist_ok=True)

    reset_logger()
    setup_logger('', log_file=(runtime_config.output_dir / 'stdout.log').as_posix(),
                 log_level=logging.DEBUG if runtime_config.debug else logging.INFO)

    global _runtime_config
    _runtime_config = runtime_config

    return runtime_config


def print_config(config, dump_config=True, output_dir=None):
    class Encoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Enum):
                return obj.value
            return super().default(obj)

    if isinstance(config, dict):
        config_meta = None
    else:
        if output_dir is None:
            output_dir = config.runtime.output_dir
        config_meta = config.meta()
        config = dataclasses.asdict(config)

    print_log('Config: ' + json.dumps(config, cls=Encoder), __name__)
    if config_meta is not None:
        print_log('Config (meta): ' + json.dumps(config_meta, cls=Encoder), __name__)
    print_log('Config (expanded):\n' + pprint.pformat(config), __name__)
    if dump_config:
        with open(os.path.join(output_dir, 'config.json'), 'w') as fh:
            json.dump(config, fh, cls=Encoder)


def get_runtime_config():
    assert _runtime_config is not None, 'Runtime config is not initialized. Please call `setup_experiment()` first.'
    return _runtime_config


def get_output_dir() -> Path:
    return get_runtime_config().output_dir


def get_checkpoint_dir() -> Path:
    return get_runtime_config().checkpoint_dir


def get_tb_log_dir() -> Path:
    return get_runtime_config().tb_log_dir


def is_debugging() -> bool:
    return get_runtime_config().debug

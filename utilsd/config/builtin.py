from pathlib import Path
from typing import Optional

from .python import configclass


@configclass
class RuntimeConfig:
    """Built-in runtime config that supports most commonly used
    fields for a deep learning experiment, including:
    
    * ``seed`` (int)
    * ``output_dir`` (path)
    * ``checkpoint_dir`` (path)
    * ``tb_log_dir`` (path)
    * ``debug`` (bool, default false)
    * ``use_cuda`` (bool, default true)

    This can be used as an argument to setup an experiment:
    :meth:`~utilsd.experiment.setup_experiment`.
    """
    seed: int = 42
    output_dir: Optional[Path] = None
    checkpoint_dir: Optional[Path] = None
    tb_log_dir: Optional[Path] = None
    debug: bool = False
    use_cuda: bool = True

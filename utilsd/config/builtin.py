from dataclasses import dataclass
from typing import Optional

from .python import PythonConfig


@dataclass(init=False)
class RuntimeConfig(PythonConfig):
    seed: int = 42
    output_dir: Optional[str] = None
    checkpoint_dir: Optional[str] = None
    tb_log_dir: Optional[str] = None
    log_dir: Optional[str] = None
    debug: bool = False

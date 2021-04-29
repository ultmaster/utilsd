from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .python import PythonConfig


@dataclass(init=False)
class RuntimeConfig(PythonConfig):
    seed: int = 42
    output_dir: Optional[Path] = None
    checkpoint_dir: Optional[Path] = None
    tb_log_dir: Optional[Path] = None
    debug: bool = False
    use_cuda: bool = True

    def check_path(self, path):
        return True

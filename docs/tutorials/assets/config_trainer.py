from enum import Enum
from typing import Optional, Tuple, Union, List, Dict, Any
from utilsd.config import configclass

class OptimizerType(str, Enum):
    SGD = 'sgd'
    Adam = 'adam'

@configclass
class OptimizerConfig:
    opt_type: OptimizerType
    learning_rate: float
    momentum: float
    weight_decay: float
    grad_clip: Optional[float]   # optional but must set, either set to none or a float
    betas: Optional[Tuple[float, float]] = None
    other_params: Optional[Dict[str, Any]] = None

@configclass
class TrainerConfig:
    optimizer: OptimizerConfig
    num_epochs: Union[int, List[int]]
    batch_size: int
    fast_dev_run: bool = False

config = TrainerConfig.fromcli()
print(config)

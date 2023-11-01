import os
import sys
import json
import tempfile
from pathlib import Path

try: 
    import torch
    test_torch = True
except ImportError:
    test_torch = False

from utilsd.config import RegistryConfig, ClassConfig, configclass, RuntimeConfig, PythonConfig, Registry
from utilsd.experiment import (
    get_checkpoint_dir,
    get_config_types,
    get_output_dir,
    get_tb_log_dir,
    get_runtime_config,
    is_debugging,
    print_config,
    setup_experiment,
    use_cuda,
)

import pytest


def test_setup_experiment():
    with pytest.raises(AssertionError):
        # raise AssertionError when cruntime_config is not intialized
        config = get_runtime_config()


    # Create a temporary directory for the experiment
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up the experiment
        runtime_config = RuntimeConfig(
            output_dir=Path(tmpdir),
            seed=123,
            debug=True,
        )
        _ = setup_experiment(runtime_config)

        runtime_config_to_check = get_runtime_config()
        assert runtime_config_to_check.output_dir ==  get_output_dir() == Path(tmpdir)
        assert runtime_config_to_check.checkpoint_dir == get_checkpoint_dir() == Path(tmpdir) / "checkpoints"
        assert runtime_config_to_check.tb_log_dir == get_tb_log_dir() == Path(tmpdir) / "tb"
        assert runtime_config_to_check.seed == 123
        assert runtime_config_to_check.debug == is_debugging() == True

        # Check that PyTorch is using CUDA if available
        if test_torch or "torch" in sys.modules:
            assert use_cuda() == (runtime_config_to_check.use_cuda and torch.cuda.is_available())


from tests.assets.exp_config.RegClass import DummyReg, Reg
from tests.assets.exp_config.TestClass import DummyClass

@configclass
class ExpConfig(PythonConfig):
    reg: RegistryConfig[DummyReg]
    clss: ClassConfig[DummyClass]
    int_var: int = 1
    runtime: RuntimeConfig = RuntimeConfig()

# Define a configuration dictionary
with tempfile.TemporaryDirectory() as tmpdir:
    config = ExpConfig.fromdict({
        "reg": {
            "type": "Reg",
            "a": 1,
            "b": "hello",
        },
        "clss": {
            "c": 2,
            "d": "world",
        },
        "int_var": 3,
        "runtime": {
            "output_dir": tmpdir,
            "debug": True,
        }
    })


def test_get_config_types():
    # Get the types of the configuration values
    types = get_config_types(config)
    # Check that the types are correct
    assert types["_config_type_name"] == ExpConfig.__name__
    assert types["reg"]["_config_type_name"] == Reg.__name__ + "Config"
    assert types["reg"]["_type_module"] == Reg.__module__
    assert types["reg"]["_type_name"] == Reg.__name__
    assert types["clss"]["_config_type_name"] == DummyClass.__name__ + "Config"
    assert types["clss"]["_type_module"] == DummyClass.__module__
    assert types["clss"]["_type_name"] == DummyClass.__name__
    assert types["runtime"]["_config_type_name"] == RuntimeConfig.__name__
    assert "_type_name" not in types["runtime"] # RuntimeConfig doesn't have a type() method
    assert "int_var" not in types # Non-dict or Non-dataclass values should not be included


def test_print_config():
    # Print the configuration
    with tempfile.TemporaryDirectory() as tmpdir:
        print_config(config, output_dir=tmpdir, retain_types=True)

        with open(os.path.join(tmpdir, "config.json")) as fh:
            config_to_check = json.load(fh)        
        with open(os.path.join(tmpdir, "config_type.json")) as fh:
            config_type_to_check = json.load(fh)
            
        assert config_to_check["int_var"] == 3
        assert config_to_check["reg"]["a"] == 1
        assert config_to_check["runtime"]["debug"] == True
        assert config_type_to_check["reg"]["_type_module"] == Reg.__module__

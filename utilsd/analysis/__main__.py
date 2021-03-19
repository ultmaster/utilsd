import argparse
import json
import logging
import os
import yaml

from .builtins import get_builtin_pattern
from .pattern import Pattern
from .pipeline import run
from .utils import prepare_logger

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser("Analysis Tool")
    parser.add_argument("config")
    parser.add_argument("--output", default=None, type=str)
    parser.add_argument("--debug", default=False, action="store_true")
    args = parser.parse_args()
    prepare_logger(args.debug)
    with open(args.config) as f:
        config = yaml.safe_load(f)
    log_paths = config["logs"]
    output_path = args.output
    if output_path is None:
        default_output_dir = "outputs/analysis"
        default_output_path = os.path.basename(args.config).rsplit(".", 1)[0].replace("/", "_").replace(".", "_").lstrip("_") + ".json"
        default_output_path = os.path.join(default_output_dir, default_output_path)
        logger.info("Using default output path: %s", default_output_path)
        output_path = default_output_path
    patterns = {}
    for name, pattern_name in config.get("builtinPatterns", {}).items():
        patterns[name] = get_builtin_pattern(pattern_name)
    for name, pattern_dict in config.get("customPatterns", {}).items():
        patterns[name] = Pattern(pattern_dict)
    result = run(log_paths, patterns)
    with open(output_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()

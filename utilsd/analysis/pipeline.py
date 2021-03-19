import glob
import logging


logger = logging.getLogger(__name__)


def analyze(log_paths: list, patterns: dict) -> dict:
    results = {}
    for log_path_pattern in log_paths:
        for log_path in glob.glob(log_path_pattern):
            logger.info("Processing '%s'", log_path)
            with open(log_path) as f:
                lines = f.readlines()
            r = dict()
            for pattern_name, pattern in patterns.items():
                r[pattern_name] = pattern.parse(lines)
                if not r[pattern_name]:
                    logger.warning("Key '%s' in '%s' is found to be: %s", pattern_name, log_path, r[pattern_name])
            results[log_path] = r
    return results

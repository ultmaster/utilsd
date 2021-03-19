import io
import logging
import os
import re
import sys
from typing import Dict, List, Union, Tuple, Callable

from collections import defaultdict


def read_log(log_file):
    if os.path.isfile(log_file):
        with open(log_file) as f:
            return list(f.readlines())
    else:
        return []


def search_for(contents: List[str], regex: str, postproc: Union[Tuple[int, Callable], Dict[int, Callable]], keepall=False):
    # postproc should be an OrderedDict
    result = []
    for line in contents:
        match = re.search(regex, line)
        if match is not None:
            if isinstance(postproc, tuple):
                found = postproc[1](match.group(postproc[0]))
            else:
                found = [p(match.group(i)) for i, p in postproc.items()]
            if not keepall:
                return found
            result.append(found)
    if not keepall:
        if isinstance(postproc, tuple):
            return None
        return tuple([None] * len(postproc))
    return result


def prepare_logger(debug_mode):
    time_format = "%m/%d %H:%M:%S"
    fmt = "[%(asctime)s] %(levelname)s (%(name)s) %(message)s"
    formatter = logging.Formatter(fmt, time_format)
    logger = logging.getLogger("analysis")
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

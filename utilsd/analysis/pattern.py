import json
import logging
import re


def plugin_sequence_group(matched_results):
    last_key = None
    results = []
    for k in matched_results:
        assert len(k) > 1
        if last_key is not None and k[0] > last_key:
            results[-1].append(k[1:])
        else:
            results.append([k[1:]])
        last_key = k[0]
    return results


def plugin_keep_first(matched_results):
    if len(matched_results) > 0:
        return matched_results[0]
    return None


def plugin_keep_last(matched_results):
    if len(matched_results) > 0:
        return matched_results[-1]
    return None


CONVERTER_DICT = {
    "int": int,
    "float": float,
    "str": str,
    "json": json.loads,
    "eval": eval,
    "none": None,
}

PLUGIN_DICT = {
    "sequence_group": plugin_sequence_group,
    "keep_first": plugin_keep_first,
    "keep_last": plugin_keep_last,
}


logger = logging.getLogger(__name__)


class Pattern:
    def __init__(self, pattern_dict):
        self.regex = re.compile(pattern_dict["pattern"])
        self.converter = [CONVERTER_DICT[k] for k in pattern_dict["converter"]]
        assert len(self.converter) == self.regex.groups
        self.plugins = [PLUGIN_DICT[k] for k in pattern_dict.get("plugins", [])]
        logger.info("Found %d converters, %d plugins.", len(self.converter), len(self.plugins))

    def parse(self, file_content):
        results = []
        for line in file_content:
            m = self.regex.search(line)
            if m is not None:
                r = [conv(m.group(i)) for i, conv in enumerate(self.converter, start=1) if conv is not None]
                if len(self.converter) == 1:
                    r = r[0]
                results.append(r)
        for plugin in self.plugins:
            results = plugin(results)
        return results

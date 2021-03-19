from .pattern import Pattern


BUILTIN_PATTERNS = {
    "config": {
        "pattern": r"ARGPARSE: (\{.*\})",
        "converter": ["json"],
        "plugins": ["keep_first"],
    }
}

def get_builtin_pattern(name):
    assert name in BUILTIN_PATTERNS, f"'{name}' not found in built-in patterns."
    return Pattern(BUILTIN_PATTERNS[name])

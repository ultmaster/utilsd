import os
import sys
from pathlib import Path


def find_secret_file(rel_path) -> Path:
    paths = [Path('~/.secrets').expanduser() / rel_path]
    current_dir = Path.cwd()
    while not current_dir.parent == current_dir:
        paths.append(current_dir / '.secrets' / rel_path)
        current_dir = current_dir.parent
    for path in paths:
        if path.exists():
            return path
    raise FileNotFoundError(f'Secret key "{rel_path}" not found.')


def run_command(command):
    print('+', command)
    if os.system(command) != 0:
        sys.exit(1)

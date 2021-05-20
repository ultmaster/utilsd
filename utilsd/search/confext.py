import argparse
import copy
import random
import os

import yaml

from ..fileio import load


def _eject_ordered_dict(obj):
    from collections import OrderedDict
    if isinstance(obj, OrderedDict):
        return {k: _eject_ordered_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_eject_ordered_dict(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _eject_ordered_dict(v) for k, v in obj.items()}
    return obj


def _import(target: str):
    if target is None:
        return None
    path, identifier = target.rsplit('.', 1)
    module = __import__(path, globals(), locals(), [identifier])
    return getattr(module, identifier)


def default_convert(config):
    config['_meta'] = copy.deepcopy(config)
    config.setdefault('runtime', {})
    config['runtime']['seed'] = random.randint(0, 10000)
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('library', type=str)
    parser.add_argument('--index', '-i', type=int)
    parser.add_argument('--converter')
    parser.add_argument('--base')
    parser.add_argument('--output', '-o', default='./outputs/config.yml')
    args = parser.parse_args()

    if args.library == 'nni':
        import nni
        data = nni.get_next_parameter()
    else:
        data = load(args.library)

    if args.index is not None:
        data = data[args.index]

    if args.converter is not None:
        if args.converter == 'default':
            data = default_convert(data)
        else:
            data = _import(args.converter)(data)
    if args.base is not None:
        data['_base_'] = os.path.abspath(args.base)

    data = _eject_ordered_dict(data)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        yaml.safe_dump(data, f)

    print(f'Saved config to {args.output}')

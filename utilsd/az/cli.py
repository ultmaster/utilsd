import functools
import os

import click

import utilsd.fileio
from .utils import find_secret_file, run_command


print = functools.partial(print, flush=True)


@click.group()
def main():
    pass


@main.command()
@click.argument('geo')
@click.argument('dest')
@click.argument('partition')
@click.option('--delete/--no-delete', help='Sync latest deletions.', default=False)
def download(geo, dest, partition, delete):
    """
    Download PARTITION sub-folder from storage and store it under DEST.
    """
    geo_lib = utilsd.fileio.load(find_secret_file('storage.json'))
    assert geo in geo_lib, f'{geo} not found in {geo_lib.keys()}'
    assert '/' not in partition and '..' not in partition, 'Illegal partition name.'
    geo = geo_lib[geo]
    dest_folder = os.path.join(dest, partition)
    os.makedirs(dest_folder, exist_ok=True)
    run_command('azcopy sync "{}/{}/{}{}" "{}" --delete-destination={}'.format(
        geo['host'], geo['default_container'], partition, geo['secret'][geo['default_container']],
        dest_folder, 'true' if delete else 'false'))


@main.command()
@click.argument('geo')
@click.argument('src')
@click.argument('partition')
@click.option('--delete/--no-delete', help='Sync latest deletions.', default=False)
def upload(geo, src, partition, delete):
    """
    Copy PARTITION sub-folder in SRC dir to the storage.
    """
    geo_lib = utilsd.fileio.load(find_secret_file('storage.json'))
    assert geo in geo_lib, f'{geo} not found in {geo_lib.keys()}'
    assert '/' not in partition and '..' not in partition, 'Illegal partition name.'
    geo = geo_lib[geo]
    source_folder = os.path.join(src, partition)
    assert os.path.exists(source_folder), f'Source folder {source_folder} does not exist!'
    run_command('azcopy sync "{}" "{}/{}/{}{}" --delete-destination={}'.format(
        source_folder, geo['host'], geo['default_container'], partition, geo['secret'][geo['default_container']],
        'true' if delete else 'false'))


if __name__ == '__main__':
    main()

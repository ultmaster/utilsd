import os
import setuptools


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


setuptools.setup(
    name='utilsd',
    version=get_version('utilsd/__init__.py'),
    author='Yuge Zhang',
    author_email='scottyugochang@gmail.com',
    description='Common utils for deep learning.',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/ultmaster/utilsd',
    packages=setuptools.find_packages(include=['utilsd*']),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    install_requires=[
        'addict>=2.4.0',
        'click>=8.0',
        'numpy>=1.18.0',
        'pyyaml>=5.4.1',
        'yapf>=0.31.0',
        'numpy<1.22;python_version<"3.8"',
    ],
    extras_require={
        'full': ['torch>=1.7.1'],
        'docs': ['sphinx', 'nbsphinx'],
    },
    entry_points={
        'console_scripts': [
            'uazcli = utilsd.az.cli:main',
        ]
    }
)

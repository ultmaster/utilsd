import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='utilsd',
    version='0.0.3',
    author='Yuge Zhang',
    author_email='scottyugochang@gmail.com',
    description='Common utils for deep learning.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ultmaster/utilsd',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    extras_require={
        'mmcv': ['mmcv>=1.2.7'],
        'full': ['mmcv>=1.2.7', 'torch>=1.7.1'],
    }
)

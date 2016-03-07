#!/usr/bin/env python
import os
from setuptools import setup, find_packages

long_description = open(
    os.path.join(
        os.path.dirname(__file__),
        'README.rst'
    )
).read()


setup(
    name='pypager',
    author='Jonathan Slenders',
    version='0.1',
    license='LICENSE',
    url='https://github.com/jonathanslenders/pyvim',
    description='Pure Python Vi Implementation',
    long_description=long_description,
    packages=find_packages('.'),
    install_requires = [
        'prompt_toolkit==0.59',
    ],
    entry_points={
        'console_scripts': [
            'pypager = pypager.entry_points.run_pypager:run',
        ]
    },
)
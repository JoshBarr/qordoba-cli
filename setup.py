#!/usr/bin/env python
# -*- coding: utf-8 -*-
from codecs import open
from setuptools import setup

__version__ = '1.0.6'


packages = [
    'qordoba',
    'qordoba.commands'
]


def get_requirements(filename):
    with open(filename, 'r', encoding='UTF-8') as f:
        return f.read()

setup(
    name="qordoba",
    author="Qordoba",
    author_email="hello@qordoba.com",
    version=__version__,
    entry_points={'console_scripts': ['qor=qordoba.cli:main', 'qordoba=qordoba.cli:main']},
    description="Qordoba command line tool",
    url="https://www.qordoba.com",
    download_url = 'https://github.com/Qordobacode/qordoba-cli/tarball/1.0.5',
    dependency_links=[],
    setup_requires=[],
    install_requires=get_requirements('requirements.txt').splitlines(),
    data_files=[],
    test_suite="tests",
    zip_safe=False,
    packages=packages,
    include_package_data=True,
    package_data={},
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)

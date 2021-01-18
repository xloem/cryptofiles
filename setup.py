#!/usr/bin/env python3

import setuptools
import cryptofiles

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()
with open('LICENSE', 'r', encoding='utf-8') as fh:
    long_description += '\n\n' + fh.read()

setuptools.setup(
    name='cryptofiles',
    version=cryptofiles.__version__,
    author='xloem',
    author_email='0xloem@gmail.com',
    description='for working with blockchained files',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/xloem/cryptofiles',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from setuptools import setup
import re
import os
import sys

# load version form _version.py
VERSIONFILE = "controlunit/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

# module

setup(
    name="controlunit",
    version=verstr,
    author="AK",
    author_email="queezz@gmail.com",
    description=("Plasma control unit"),
    license="BSD 3-clause",
    keywords="control",
    url="https://github.com/queezz/ControlUnit",
    packages=["controlunit"],
    package_dir={"controlunit": "controlunit"},
    py_modules=["controlunit.__init__"],
    # test_suite="testings",
    install_requires="""
        numpy>=1.10
        matplotlib>=3.0
        pandas>=1.3
        pqtgraph>0.1
      """,
    package_data={"": [".settings"]},
    include_package_data=True,
    scripts=["bin/plasmacontrol"],
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.6",
        "Topic :: Scientific/Engineering :: Physics",
    ],
)


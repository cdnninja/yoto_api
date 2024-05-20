#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

long_description = readme + "\n\n" + history
long_description = readme

test_requirements = [
    "pytest>=3",
]

setup(
    author="cdnninja",
    author_email="",
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.9",
    ],
    description="A python package that makes it a bit easier to work with the yoto play API. Not associated with Yoto in any way.",
    install_requires=requirements,
    license="MIT license",
    long_description=long_description,
    include_package_data=True,
    keywords="yoto_api",
    name="yoto_api",
    packages=find_packages(include=["yoto_api", "yoto_api.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/cdnninja/yoto_api",
    version="1.15.2",
    zip_safe=False,
)

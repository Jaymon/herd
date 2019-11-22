#!/usr/bin/env python
from setuptools import setup, find_packages
import re
import os
from codecs import open


name = "herd"

kwargs = {"name": name}

def read(path):
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            return f.read()
    return ""


vpath = os.path.join(name, "__init__.py")
if os.path.isfile(vpath):
    kwargs["packages"] = find_packages(exclude=["tests", "tests.*", "*_test*", "examples"])
else:
    vpath = "{}.py".format(name)
    kwargs["py_modules"] = [name]
kwargs["version"] = re.search(r"^__version__\s*=\s*[\'\"]([^\'\"]+)", read(vpath), flags=re.I | re.M).group(1)


kwargs["long_description"] = read('README.md')
kwargs["long_description_content_type"] = "text/markdown"

kwargs["tests_require"] = ["testdata"]
kwargs["install_requires"] = ["boto3", "captain"]


setup(
    description='Quickly and easily create AWS lambda python functions and make them available from a url',
    keywords="aws sysadmin serverless function lambda",
    author='Jay Marcyes',
    author_email='jay@marcyes.com',
    url='http://github.com/Jaymon/{}'.format(name),
    license="MIT",
    classifiers=[ # https://pypi.python.org/pypi?:action=list_classifiers
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        #'Programming Language :: Python :: 3',
    ],
    entry_points = {
        'console_scripts': [
            '{} = {}.__main__:main'.format(name, name),
        ],
    },
    **kwargs
)


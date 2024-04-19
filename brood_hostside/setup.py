from setuptools import setup

import codecs
import os.path

# for importing the version from the package, read() and get_version()
# see https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")

setup(name="brood_hostside",
    version=get_version("brood_hostside/__init__.py"),
    description="Code to manage broodnest robot from (linux) host",
    author="Rob Mills, Daniel Hofstadler, Rafael Barmak",
    author_email="rob.mills@epfl.ch",
    license='MIT',
    packages=["brood_hostside", "brood_hostside/src"],
    install_requires=[
        "pyserial>=3.4",
        "influxdb-client>=1.36",
        #numpy # much more efficient to use apt python3-numpy for constrained devices
        ],

    data_files=[
                ('brood_hostside/runtime_tools', [
                    'runtime_tools/abc_read.py',
                    'runtime_tools/abc_run.py'
                ]),
                ('brood_hostside/runtime_tools/cfg', [
                    'runtime_tools/cfg/example.cfg',
                ]),

                ('brood_hostside/docs', [
                    'docs/ho-brood-hostside.pdf'
                ]),
                ],
    include_package_data=True
    )


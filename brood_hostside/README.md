# Packaging the brood-hostside library

RM, RB, EPFL; DH, UniGraz. 2021-2024

- Main class : `brood_hostside.libabc.ABCHandle`
- Main entry point: `runtime_tools/abc_run.py`

See doc directory for API and some usage notes.

## Installation

- the dependencies can be handled by pip, but since installing numpy from 
  pre-compiled binaries is so much faster (especially on constrained 
  devices), we recommend using those.

```bash
# install on debian
sudo apt install python3-numpy
# install on fedora
sudo dnf install python3-numpy
```

- for development mode, you can use

`pip3 install --editable .`


## Rebuild docs (sphinx)

```bash
cd <root>/docs/source
make latexpdf
evince ./build/latex/ho-brood-hostside.pdf &
```


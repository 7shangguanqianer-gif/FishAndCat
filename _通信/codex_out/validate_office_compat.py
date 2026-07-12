"""Run the bundled Office validator with the host's pure-Python defusedxml.

The bundled Python is 3.12 and has the Office validator's other dependencies,
while the host 3.9 environment supplies defusedxml. Appending that site path
keeps the bundled binary packages ahead of incompatible host wheels.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


if len(sys.argv) != 3:
    raise SystemExit("usage: validate_office_compat.py VALIDATOR TARGET")

validator, target = sys.argv[1:]
sys.path.append(r"D:\py\Python3\lib\site-packages")
sys.path.insert(0, str(Path(validator).resolve().parent))
sys.argv = [validator, target]
runpy.run_path(validator, run_name="__main__")

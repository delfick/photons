import os
import runpy
import sys
from pathlib import Path

deps_dir = Path(__file__).parent / "deps"
if not deps_dir.exists():
    deps_dir.mkdir()

if not (deps_dir / "venvstarter.py").exists():
    os.system(f"{sys.executable} -m pip install venvstarter -t {deps_dir}")

venvstarter_module = runpy.run_path(str(deps_dir / "venvstarter.py"))

wanted_version = "0.11.0"

upgrade = False
VERSION = venvstarter_module.get("VERSION")
if VERSION is None:
    upgrade = True
else:
    Version = venvstarter_module["Version"]
    if Version(wanted_version) < Version(VERSION):
        upgrade = True

if upgrade:
    os.system(f"{sys.executable} -m pip install 'venvstarter>={wanted_version}' -t {deps_dir}")

manager = runpy.run_path(str(deps_dir / "venvstarter.py"))["manager"]
